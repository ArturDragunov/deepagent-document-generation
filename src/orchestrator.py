"""Async orchestrator for the 6-manager BRD generation pipeline.

Architecture:
  - 6 managers: Drool, Model, Outbound, Transformation, Inbound, Reviewer
  - Each manager has specialized sub-agents (handled by deepagents internally)
  - Execution flow:
    1. Drool + Model run IN PARALLEL (asyncio.gather)
    2. Outbound -> Transformation -> Inbound run SEQUENTIALLY
    3. Reviewer validates; if gaps found, requests manager reruns (max retries)

  - Uses ainvoke() for true async (deepagents CompiledStateGraph supports it)
  - Structured logging via structlog
  - Token/cost tracking per manager
"""

import asyncio
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.config import get_config
from src.guardrails import get_input_guardrail
from src.logger import get_logger
from src.models import (
  ExecutionContext,
  ExecutionResult,
  AgentMessage,
  MessageStatus,
  AgentType,
  TokenTracker,
  ReprocessRequest,
)
from src.agents.agent_definitions import create_all_managers

logger = get_logger(__name__)


class BRDOrchestrator:
  """Async orchestrator for the 6-manager BRD generation pipeline."""

  def __init__(self):
    self.config = get_config()
    self.guardrail = get_input_guardrail()
    self.managers: Dict[str, Any] = {}
    self.context: Optional[ExecutionContext] = None

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
    """Run the full BRD generation pipeline.

    Args:
        user_query: User's input query.
        corpus_files: List of corpus file paths (relative to corpus dir).
        golden_brd_path: Optional path to golden BRD reference.
        output_dir: Output directory for results.

    Returns:
        ExecutionResult with status, messages, tokens, and metadata.
    """
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

    # Create all managers
    self.managers = create_all_managers(
      model=self.config.llm_model,
      model_provider=self.config.llm_model_provider,
    )

    logger.info(
      "pipeline_started",
      execution_id=self.context.execution_id,
      query=user_query[:200],
      corpus_files=len(corpus_files),
      model=self.config.llm_model,
    )

    try:
      # Phase 1: Drool + Model in parallel
      logger.info("phase_1_parallel", agents=["drool", "model"])
      drool_msg, model_msg = await self._run_parallel_phase()
      self._record_message(drool_msg, "drool")
      self._record_message(model_msg, "model")

      # Phase 2: Sequential cascade
      logger.info("phase_2_sequential", agents=["outbound", "transformation", "inbound"])
      for name in ["outbound", "transformation", "inbound"]:
        msg = await self._execute_manager(name)
        self._record_message(msg, name)

      # Phase 3: Reviewer with feedback loop
      logger.info("phase_3_reviewer")
      reviewer_msg = await self._run_reviewer_loop()
      self._record_message(reviewer_msg, "reviewer")

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
  # Phase execution
  # ------------------------------------------------------------------

  async def _run_parallel_phase(
    self,
  ) -> Tuple[Optional[AgentMessage], Optional[AgentMessage]]:
    """Run Drool and Model in parallel via asyncio.gather."""
    try:
      drool_msg, model_msg = await asyncio.gather(
        self._execute_manager("drool"),
        self._execute_manager("model"),
        return_exceptions=False,
      )
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

  async def _execute_manager(
    self,
    name: str,
    feedback: Optional[ReprocessRequest] = None,
  ) -> Optional[AgentMessage]:
    """Execute a single manager agent with timeout."""
    if name not in self.managers:
      logger.error("unknown_manager", name=name)
      return None

    manager = self.managers[name]
    start = time.time()

    try:
      user_message = self._build_prompt(name, feedback)

      # Use ainvoke for true async execution
      try:
        result = await asyncio.wait_for(
          manager.ainvoke({"messages": [{"role": "user", "content": user_message}]}),
          timeout=self.config.agent_timeout_sec,
        )
      except asyncio.TimeoutError:
        duration = (time.time() - start) * 1000
        logger.error("manager_timeout", name=name, timeout=self.config.agent_timeout_sec)
        return AgentMessage(
          agent_id=name,
          agent_type=AgentType.MANAGER,
          status=MessageStatus.TIMEOUT,
          markdown_content="",
          metadata={"error": f"Timeout after {self.config.agent_timeout_sec}s"},
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
    """Extract content and metadata from deepagents invoke result."""
    content = ""
    metadata = {}

    if isinstance(result, dict):
      if "messages" in result:
        messages = result["messages"]
        if isinstance(messages, list) and messages:
          last = messages[-1]
          content = last.content if hasattr(last, "content") else str(last)
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
      self._record_message(msg, agent_id)

  # ------------------------------------------------------------------
  # Prompt building
  # ------------------------------------------------------------------

  def _build_prompt(
    self,
    name: str,
    feedback: Optional[ReprocessRequest] = None,
  ) -> str:
    """Build context-aware prompt for a manager."""
    prior_context = self._get_prior_context(name)

    prompt = (
      f"User Query: {self.context.user_query}\n"
      f"Corpus Files: {', '.join(self.context.corpus_files[:20])}\n\n"
    )

    if prior_context:
      prompt += f"Previous Agent Outputs:\n{prior_context}\n\n"

    if feedback:
      prompt += (
        f"REPROCESSING REQUEST:\n"
        f"Feedback: {feedback.feedback}\n"
        f"Missing: {', '.join(feedback.missing_items)}\n\n"
        f"Address the gaps above and update your output.\n"
      )
    else:
      prompt += "Analyze the query and corpus files. Generate comprehensive output for your domain.\n"

    return prompt

  def _get_prior_context(self, name: str) -> str:
    """Get relevant prior outputs for a manager based on dependency chain."""
    deps = {
      "drool": [],
      "model": [],
      "outbound": ["drool", "model"],
      "transformation": ["drool", "model", "outbound"],
      "inbound": ["drool", "model", "outbound", "transformation"],
      "reviewer": ["drool", "model", "outbound", "transformation", "inbound"],
    }.get(name, [])

    parts = []
    for msg in self.context.all_messages:
      if msg.agent_id in deps and msg.markdown_content:
        # Truncate to keep context manageable
        content = msg.markdown_content[:2000]
        parts.append(f"## {msg.agent_id.upper()} Output:\n{content}")

    return "\n\n".join(parts)

  # ------------------------------------------------------------------
  # Helpers
  # ------------------------------------------------------------------

  def _record_message(self, msg: Optional[AgentMessage], name: str) -> None:
    """Record a message to execution context."""
    if msg:
      self.context.add_message(msg)
      if msg.status == MessageStatus.SUCCESS:
        logger.info("message_recorded", agent=name, duration_ms=round(msg.duration_ms, 1))
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
