"""Async orchestrator for the 6-manager BRD generation pipeline.

Architecture (simplified -- no sub-agents):
  - 6 flat managers: Drool, Model, Outbound, Transformation, Inbound, Reviewer
  - Execution flow:
    1. Pre-filter drool files via LLM-based filter
    2. Drool + Model run IN PARALLEL (asyncio.gather)
    3. Outbound -> Transformation -> Inbound run SEQUENTIALLY
       Each step receives ALL prior outputs via file-based sharing
    4. Reviewer validates; if gaps found, requests manager reruns (max retries)

  - Agent outputs saved to files -- downstream agents read full content via
    read_agent_output tool. NO truncation on data flow.
  - Uses ainvoke() for true async (deepagents CompiledStateGraph supports it)
  - ExecutionLogger callback for LLM/tool call visibility
"""

import asyncio
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.config import get_config
from src.execution_logging import ExecutionLogger
from src.guardrails import get_input_guardrail
from src.logger import get_logger
from src.models import (
  ExecutionContext,
  ExecutionResult,
  AgentMessage,
  MessageStatus,
  AgentType,
  ReprocessRequest,
)
from src.agents.agent_definitions import create_all_managers
from src.tools.drool_filter import filter_drool_files
from src.tools.agent_output import save_agent_output, clear_agent_outputs

logger = get_logger(__name__)


def group_files_by_workbook(
  files: List[str],
  delimiter: str,
  max_per_group: Optional[int] = None,
) -> List[List[str]]:
  """Group file paths by workbook key (prefix before delimiter). Split groups larger than max_per_group."""
  if not files:
    return []
  if not delimiter:
    flat = [[f] for f in files]
    if max_per_group and max_per_group > 0:
      return _chunk_groups(flat, max_per_group)
    return flat
  groups: Dict[Tuple[str, str], List[str]] = {}
  for path in files:
    p = Path(path)
    parent = str(p.parent) if p.parent != Path(".") else ""
    name = p.name
    if delimiter in name:
      key = (parent, name.split(delimiter)[0])
    else:
      key = (parent, name)
    groups.setdefault(key, []).append(path)
  ordered = sorted(groups.items(), key=lambda x: x[0])
  result: List[List[str]] = [g for _, g in ordered]
  if max_per_group and max_per_group > 0:
    result = _chunk_groups(result, max_per_group)
  return result


def _chunk_groups(groups: List[List[str]], max_per: int) -> List[List[str]]:
  """Split any group with more than max_per files into chunks of max_per."""
  out: List[List[str]] = []
  for g in groups:
    if len(g) <= max_per:
      out.append(g)
    else:
      for i in range(0, len(g), max_per):
        out.append(g[i : i + max_per])
  return out


def _message_content_to_str(raw: Any) -> str:
  """Normalize AIMessage/last message content to str (content can be list of blocks)."""
  if raw is None:
    return ""
  if isinstance(raw, str):
    return raw
  if isinstance(raw, list):
    parts = []
    for block in raw:
      if isinstance(block, str):
        parts.append(block)
      elif isinstance(block, dict) and "text" in block:
        parts.append(block["text"])
      else:
        parts.append(str(block))
    return "\n".join(parts)
  return str(raw)


class BRDOrchestrator:
  """Async orchestrator for the 6-manager BRD generation pipeline."""

  def __init__(self):
    self.config = get_config()
    self.guardrail = get_input_guardrail()
    self.managers: Dict[str, Any] = {}
    self.context: Optional[ExecutionContext] = None
    self._drool_files: List[str] = []
    self._non_drool_files: List[str] = []
    self._completed_agents: List[str] = []
    self._golden_brd_path: Optional[Path] = None

    logger.info(
      "orchestrator_initialized",
      model=self.config.llm_model,
      provider=self.config.llm_model_provider or "default",
    )

  async def run_pipeline(
    self,
    user_query: str,
    corpus_files: List[str],
    golden_brd_path: Optional[Path] = None,
    output_dir: Optional[Path] = None,
  ) -> ExecutionResult:
    """Run the full BRD generation pipeline."""
    # Validate input
    is_valid, violations = self.guardrail.validate_input(user_query)
    if not is_valid:
      summary = self.guardrail.get_violation_summary(violations)
      logger.error("input_validation_failed", summary=summary)
      return ExecutionResult(
        status=MessageStatus.ERROR,
        errors=[summary],
        execution_id=str(uuid.uuid4()),
      )

    # Init execution context
    output_dir = output_dir or self.config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    self.context = ExecutionContext(
      user_query=user_query,
      corpus_files=corpus_files,
      output_dir=output_dir,
      max_timeout_sec=self.config.agent_timeout_sec,
      retry_count=self.config.max_retries,
      execution_id=str(uuid.uuid4()),
    )

    # Clear previous agent outputs (offload sync I/O)
    await asyncio.to_thread(clear_agent_outputs)
    self._completed_agents = []

    # Categorize files: drool (.drl) vs non-drool
    self._drool_files = [f for f in corpus_files if f.endswith(".drl")]
    self._non_drool_files = [f for f in corpus_files if not f.endswith(".drl")]

    self._golden_brd_path = golden_brd_path if golden_brd_path is not None else self.config.golden_brd_path

    # Create all managers
    self.managers = create_all_managers(
      model=self.config.llm_model,
      model_provider=self.config.llm_model_provider,
    )

    logger.info(
      "pipeline_started",
      execution_id=self.context.execution_id,
      query=user_query,
      corpus_files=len(corpus_files),
      drool_files=len(self._drool_files),
      non_drool_files=len(self._non_drool_files),
      model=self.config.llm_model,
    )

    try:
      # Phase 0: Pre-filter drool files via LLM
      filtered_drool = await self._filter_drool_files(user_query)

      # Phase 1: Drool + Model in parallel (Model runs per workbook group)
      logger.info("phase_1_parallel", agents=["drool", "model"])
      drool_msg, model_msg = await self._run_parallel_phase(filtered_drool)
      await self._record_and_save(drool_msg, "drool")
      # Model output already saved and messages added by _run_manager_grouped

      # Phase 2: Sequential cascade -- each runs per workbook group, merges markdown
      logger.info("phase_2_sequential", agents=["outbound", "transformation", "inbound"])
      for name in ["outbound", "transformation", "inbound"]:
        logger.info("phase_2_step", manager=name)
        await self._run_manager_grouped(name, self._non_drool_files)

      # Phase 3: Reviewer with feedback loop
      logger.info("phase_3_reviewer")
      reviewer_msg = await self._run_reviewer_loop()
      await self._record_and_save(reviewer_msg, "reviewer")

      # Finalize
      elapsed = self.context.get_elapsed_time_sec()
      logger.info(
        "pipeline_completed",
        elapsed_sec=round(elapsed, 2),
        messages=len(self.context.all_messages),
        token_summary=self.context.token_tracker.get_summary(),
      )

      return ExecutionResult(
        status=MessageStatus.SUCCESS,
        all_messages=self.context.all_messages,
        token_summary=self.context.token_tracker.get_summary(),
        execution_time_sec=elapsed,
        execution_id=self.context.execution_id,
        warnings=self._collect_warnings(),
      )

    except Exception as e:
      elapsed = self.context.get_elapsed_time_sec()
      logger.error("pipeline_failed", error=str(e), elapsed_sec=round(elapsed, 2))
      return ExecutionResult(
        status=MessageStatus.ERROR,
        all_messages=self.context.all_messages,
        token_summary=self.context.token_tracker.get_summary(),
        execution_time_sec=elapsed,
        errors=[str(e)],
        execution_id=self.context.execution_id,
      )

  # ------------------------------------------------------------------
  # Drool file filtering
  # ------------------------------------------------------------------

  async def _filter_drool_files(self, user_query: str) -> List[str]:
    """Pre-filter drool files using LLM-based relevance check."""
    if not self._drool_files:
      logger.info("drool_filter_skip", reason="no .drl files in corpus")
      return []

    logger.info("drool_filter_start", files=len(self._drool_files))
    result = await filter_drool_files(user_query, self._drool_files)
    filtered = result.get("included", [])
    logger.info(
      "drool_filter_done",
      included=len(filtered),
      excluded=len(result.get("excluded", [])),
    )
    return filtered

  # ------------------------------------------------------------------
  # Phase execution
  # ------------------------------------------------------------------

  async def _run_manager_grouped(
    self, name: str, files: List[str],
  ) -> Optional[AgentMessage]:
    """Run a manager per workbook group (capped size) in parallel; merge markdown; optionally consolidate with golden BRD."""
    groups = group_files_by_workbook(
      files,
      self.config.file_group_delimiter,
      max_per_group=self.config.max_files_per_group,
    )
    if not groups:
      return None

    for idx, group in enumerate(groups):
      logger.info(
        "phase_group_step",
        manager=name,
        group=idx + 1,
        total_groups=len(groups),
        files_in_group=len(group),
      )

    tasks = [self._execute_manager(name, file_override=group) for group in groups]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    accumulated: List[str] = []
    last_msg: Optional[AgentMessage] = None
    for idx, r in enumerate(results):
      if isinstance(r, Exception):
        logger.error("manager_group_failed", manager=name, group=idx + 1, error=str(r))
        continue
      if r:
        self.context.add_message(r)
        last_msg = r
        if r.status == MessageStatus.SUCCESS and r.markdown_content:
          accumulated.append(r.markdown_content)

    if accumulated:
      merged = "\n\n---\n\n".join(accumulated)
      await asyncio.to_thread(save_agent_output, name, merged)
      self._completed_agents.append(name)
      logger.info("message_recorded", agent=name, output_chars=sum(len(p) for p in accumulated))
      if self.config.consolidate_sections and len(accumulated) > 1:
        consolidated_msg = await self._run_consolidation(name, merged)
        if consolidated_msg and consolidated_msg.status == MessageStatus.SUCCESS and consolidated_msg.markdown_content:
          await asyncio.to_thread(save_agent_output, name, consolidated_msg.markdown_content)
          logger.info("consolidation_done", agent=name, output_chars=len(consolidated_msg.markdown_content))
    return last_msg

  def _load_golden_brd(self) -> str:
    """Load golden BRD reference content for consolidation prompts (.md or .docx)."""
    if not self._golden_brd_path:
      return ""
    p = Path(self._golden_brd_path)
    if not p.exists():
      logger.warning("golden_brd_not_found", path=str(p))
      return ""
    try:
      from src.tools.corpus_reader import read_file_as_text
      return read_file_as_text(p)
    except Exception as e:
      logger.warning("golden_brd_read_failed", path=str(p), error=str(e))
      return ""

  def _build_consolidation_prompt(self, name: str, merged_markdown: str, golden_brd_content: str) -> str:
    """Build prompt for consolidation step: turn merged sections into one coherent doc using golden BRD reference."""
    return (
      f"USER QUERY: {self.context.user_query}\n\n"
      "CONSOLIDATION TASK: You previously produced the following sections from batch processing. "
      "Produce ONE coherent markdown document with:\n"
      "- A single table of contents at the top\n"
      "- No duplicate headers; merge or deduplicate sections as needed\n"
      "- Consistent structure and formatting\n"
      "- Use the golden BRD reference below for style and expected sections\n\n"
      f"GOLDEN BRD REFERENCE:\n{golden_brd_content}\n\n"
      "MERGED SECTIONS TO CONSOLIDATE:\n"
      f"{merged_markdown}\n\n"
      "Output only the consolidated markdown document, no commentary."
    )

  async def _run_consolidation(self, name: str, merged_markdown: str) -> Optional[AgentMessage]:
    """One short run: consolidate merged sections into one coherent doc using golden BRD. No file reads."""
    golden = await asyncio.to_thread(self._load_golden_brd)
    prompt = self._build_consolidation_prompt(name, merged_markdown, golden)
    logger.info("consolidation_start", manager=name, merged_len=len(merged_markdown))
    return await self._execute_manager(name, prebuilt_message=prompt, file_override=[])

  async def _run_parallel_phase(
    self,
    filtered_drool_files: List[str],
  ) -> Tuple[Optional[AgentMessage], Optional[AgentMessage]]:
    """Run Drool and Model in parallel via asyncio.gather. Model runs per workbook group."""
    try:
      logger.info("phase_1_starting")
      drool_future = asyncio.create_task(
        self._execute_manager("drool", file_override=filtered_drool_files),
      )
      model_future = asyncio.create_task(
        self._run_manager_grouped("model", self._non_drool_files),
      )
      drool_msg, model_msg = await asyncio.gather(drool_future, model_future, return_exceptions=False)
      logger.info("phase_1_done")
      return drool_msg, model_msg
    except Exception as e:
      logger.error("parallel_phase_failed", error=str(e))
      return None, None

  async def _run_reviewer_loop(self) -> Optional[AgentMessage]:
    """Run Reviewer with feedback loop (max retries)."""
    max_iters = self.config.max_retries
    reviewer_msg = None

    for iteration in range(max_iters + 1):
      logger.info("reviewer_iteration", iteration=iteration + 1, max=max_iters + 1)
      reviewer_msg = await self._execute_manager("reviewer")

      if not reviewer_msg:
        logger.warning("reviewer_no_output")
        return None

      gaps = reviewer_msg.metadata.get("gaps", [])
      if not gaps or iteration >= max_iters:
        logger.info("reviewer_complete", iteration=iteration + 1)
        return reviewer_msg

      # Process feedback
      logger.info("reviewer_gaps_detected", count=len(gaps), iteration=iteration + 1)
      await self._process_feedback(gaps)

    return reviewer_msg

  # ------------------------------------------------------------------
  # Manager execution
  # ------------------------------------------------------------------

  def _get_timeout_sec(self, name: str) -> int:
    """Return timeout in seconds for this manager (reviewer gets longer default)."""
    return self.config.reviewer_timeout_sec if name == "reviewer" else self.config.agent_timeout_sec

  async def _execute_manager(
    self,
    name: str,
    feedback: Optional[ReprocessRequest] = None,
    file_override: Optional[List[str]] = None,
    prebuilt_message: Optional[str] = None,
  ) -> Optional[AgentMessage]:
    """Execute a single manager agent with timeout."""
    if name not in self.managers:
      logger.error("unknown_manager", name=name)
      return None

    manager = self.managers[name]
    start = time.time()
    timeout_sec = self._get_timeout_sec(name)

    logger.info("manager_started", name=name, feedback=feedback is not None)

    try:
      user_message = prebuilt_message if prebuilt_message is not None else self._build_prompt(name, feedback, file_override)

      logger.info(
        "manager_invoking",
        name=name,
        timeout_sec=timeout_sec,
        prompt_len=len(user_message),
      )

      # Use ainvoke with ExecutionLogger callback for LLM/tool visibility and token recording
      run_config = {
        "callbacks": [
          ExecutionLogger(name, token_callback=lambda mn, it, ot: self._record_tokens(mn, it, ot)),
        ],
      }
      inputs = {"messages": [{"role": "user", "content": user_message}]}

      try:
        result = await asyncio.wait_for(
          manager.ainvoke(inputs, config=run_config),
          timeout=timeout_sec,
        )
      except asyncio.TimeoutError:
        duration = (time.time() - start) * 1000
        logger.error("manager_timeout", name=name, timeout=timeout_sec)
        return AgentMessage(
          agent_id=name,
          agent_type=AgentType.MANAGER,
          status=MessageStatus.TIMEOUT,
          markdown_content="",
          metadata={"error": f"Timeout after {timeout_sec}s"},
          duration_ms=duration,
        )

      # Extract content from deepagents result
      content, metadata = self._extract_result(result)
      duration = (time.time() - start) * 1000

      logger.info(
        "manager_completed",
        name=name,
        duration_ms=round(duration, 1),
        content_len=len(content),
      )

      return AgentMessage(
        agent_id=name,
        agent_type=AgentType.MANAGER,
        markdown_content=content,
        metadata=metadata,
        duration_ms=duration,
        status=MessageStatus.SUCCESS,
      )

    except Exception as e:
      duration = (time.time() - start) * 1000
      logger.error("manager_failed", name=name, error=str(e), duration_ms=round(duration, 1))
      return AgentMessage(
        agent_id=name,
        agent_type=AgentType.MANAGER,
        status=MessageStatus.ERROR,
        markdown_content="",
        metadata={"error": str(e)},
        duration_ms=duration,
      )

  @staticmethod
  def _extract_result(result: Any) -> Tuple[str, Dict[str, Any]]:
    """Extract content and metadata from deepagents ainvoke result."""
    content = ""
    metadata = {}

    if isinstance(result, dict):
      if "messages" in result:
        messages = result["messages"]
        if isinstance(messages, list) and messages:
          last = messages[-1]
          raw = last.content if hasattr(last, "content") else str(last)
          content = _message_content_to_str(raw)
        else:
          content = str(result)
      else:
        content = str(result)
    else:
      content = str(result)

    return content, metadata

  # ------------------------------------------------------------------
  # Feedback processing
  # ------------------------------------------------------------------

  async def _process_feedback(self, gaps: List[Dict[str, Any]]) -> None:
    """Rerun affected managers based on reviewer gaps."""
    gaps_by_agent: Dict[str, List[Dict]] = {}
    for gap in gaps:
      aid = gap.get("agent_id", gap.get("manager", "unknown"))
      gaps_by_agent.setdefault(aid, []).append(gap)

    for agent_id, agent_gaps in gaps_by_agent.items():
      if agent_id not in self.managers:
        logger.warning("feedback_unknown_manager", agent_id=agent_id)
        continue

      feedback_text = "\n".join(g.get("feedback", "") for g in agent_gaps)
      missing = []
      for g in agent_gaps:
        missing.extend(g.get("missing_items", []))

      request = ReprocessRequest(
        agent_id=agent_id,
        domain=agent_gaps[0].get("domain", ""),
        feedback=feedback_text,
        context="Feedback from Reviewer after validation",
        missing_items=missing,
        retry_count=1,
      )

      logger.info("reprocessing_manager", agent_id=agent_id, gaps=len(agent_gaps))
      msg = await self._execute_manager(agent_id, feedback=request)
      await self._record_and_save(msg, agent_id)

  # ------------------------------------------------------------------
  # Prompt building
  # ------------------------------------------------------------------

  def _build_prompt(
    self,
    name: str,
    feedback: Optional[ReprocessRequest] = None,
    file_override: Optional[List[str]] = None,
  ) -> str:
    """Build context-aware prompt for a manager.

    Tells agents which prior outputs are available and how to read them
    via read_agent_output tool. No inline content -- agents read full files.
    """
    deps = self._get_dependencies(name)
    available_outputs = [d for d in deps if d in self._completed_agents]
    files = file_override if file_override is not None else self._non_drool_files

    prompt = f"USER QUERY: {self.context.user_query}\n\n"

    # Explicit file list -- agent reads these with read_corpus_file
    if files:
      file_list = "\n".join(f"  - {f}" for f in files)
      prompt += f"FILES TO ANALYZE:\n{file_list}\n\n"
      prompt += (
        "Read each file using the read_corpus_file tool. "
        "Group files by source workbook (shared prefix) and process in logical order.\n\n"
      )
    else:
      prompt += "No specific corpus files assigned. Work with the context provided.\n\n"

    # Tell agent about prior outputs -- they read full content via tool
    if available_outputs:
      output_list = "\n".join(f"  - {a} (read with: read_agent_output('{a}'))" for a in available_outputs)
      prompt += (
        f"PREVIOUS AGENT OUTPUTS AVAILABLE:\n{output_list}\n\n"
        f"Use the read_agent_output tool to read each previous agent's FULL output. "
        f"These contain the complete analysis from prior pipeline stages.\n\n"
      )

    if feedback:
      prompt += (
        f"REPROCESSING REQUEST:\n"
        f"Feedback: {feedback.feedback}\n"
        f"Missing: {', '.join(feedback.missing_items)}\n\n"
        f"Address the gaps above and update your output.\n"
      )
    else:
      prompt += (
        "Analyze the files and generate comprehensive output for your domain. "
        "Be thorough and extract all relevant information.\n"
      )

    return prompt

  @staticmethod
  def _get_dependencies(name: str) -> List[str]:
    """Get dependency list for a manager."""
    return {
      "drool": [],
      "model": [],
      "outbound": ["drool", "model"],
      "transformation": ["drool", "model", "outbound"],
      "inbound": ["drool", "model", "outbound", "transformation"],
      "reviewer": ["drool", "model", "outbound", "transformation", "inbound"],
    }.get(name, [])

  # ------------------------------------------------------------------
  # Helpers
  # ------------------------------------------------------------------

  def _record_tokens(self, manager_name: str, input_tokens: int, output_tokens: int) -> None:
    """Callback for ExecutionLogger: record token usage and cost in context."""
    if not self.context or not self.config.track_tokens:
      return
    in_t = input_tokens or 0
    out_t = output_tokens or 0
    cost = self.config.get_cost_estimate(in_t, out_t)
    self.context.token_tracker.record_estimate(
      manager_name, in_t, out_t, cost_estimate=cost,
    )

  async def _record_and_save(self, msg: Optional[AgentMessage], name: str) -> None:
    """Record message to context AND save full output to file for downstream agents."""
    if msg:
      self.context.add_message(msg)

      # Save full markdown output to file (no truncation); offload sync I/O
      if msg.status == MessageStatus.SUCCESS and msg.markdown_content:
        await asyncio.to_thread(save_agent_output, name, msg.markdown_content)
        self._completed_agents.append(name)
        logger.info(
          "message_recorded",
          agent=name,
          duration_ms=round(msg.duration_ms, 1),
          output_chars=len(msg.markdown_content),
        )
      else:
        logger.warning("message_recorded_with_issues", agent=name, status=msg.status.value)
    else:
      logger.warning("no_output", agent=name)

  def _collect_warnings(self) -> List[str]:
    """Collect warnings from execution."""
    warnings = []
    for msg in self.context.all_messages:
      if msg.status == MessageStatus.TIMEOUT:
        warnings.append(f"{msg.agent_id} timed out")
      elif msg.status == MessageStatus.PARTIAL:
        warnings.append(f"{msg.agent_id} produced partial results")
      elif msg.status == MessageStatus.ERROR:
        warnings.append(f"{msg.agent_id} encountered an error")

    summary = self.context.token_tracker.get_summary()
    if summary.get("total_cost_estimate", 0) > 10:
      warnings.append(f"High token cost: ${summary['total_cost_estimate']:.2f}")

    return warnings
