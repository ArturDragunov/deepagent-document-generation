"""Execution logging: LangChain callback handler for LLM and tool call visibility.

Provides:
  - ExecutionLogger: logs every LLM start/end and tool start/end
  - Used by the orchestrator when invoking managers
"""

from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from src.logger import get_logger

logger = get_logger(__name__)


def _content_to_str(value: Any) -> str:
  """Normalize message/tool content to string (handles ToolMessage, list of blocks)."""
  if value is None:
    return ""
  if isinstance(value, str):
    return value
  if hasattr(value, "content"):
    return _content_to_str(value.content)
  if isinstance(value, list):
    parts = []
    for block in value:
      if isinstance(block, str):
        parts.append(block)
      elif isinstance(block, dict) and "text" in block:
        parts.append(block["text"])
      else:
        parts.append(str(block))
    return "\n".join(parts)
  return str(value)


class ExecutionLogger(BaseCallbackHandler):
  """Logs every LLM call and tool call for visibility into agent execution."""

  def __init__(
    self,
    manager_name: str,
    token_callback: Optional[Callable[[str, int, int], None]] = None,
  ):
    self.manager_name = manager_name
    self._llm_call_count = 0
    self._tool_call_count = 0
    self._token_callback = token_callback

  def on_llm_start(
    self,
    serialized: Dict[str, Any],
    prompts: List[str],
    *,
    run_id: UUID,
    parent_run_id: Optional[UUID] = None,
    **kwargs: Any,
  ) -> None:
    self._llm_call_count += 1
    prompt_preview = (prompts[0][:200] + "...") if prompts and len(prompts[0]) > 200 else (prompts[0] if prompts else "")
    logger.info(
      "llm_call_started",
      manager=self.manager_name,
      call_number=self._llm_call_count,
      run_id=str(run_id),
      prompt_len=sum(len(p) for p in prompts) if prompts else 0,
      prompt_preview=prompt_preview.replace("\n", " "),
    )

  def on_llm_end(
    self,
    response: LLMResult,
    *,
    run_id: UUID,
    parent_run_id: Optional[UUID] = None,
    **kwargs: Any,
  ) -> None:
    generations = response.generations
    token_usage = getattr(response, "llm_output", None) or {}
    usage = token_usage.get("token_usage", {}) if isinstance(token_usage, dict) else {}
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    output_len = 0
    if generations:
      for g in generations:
        if g and g[0].text:
          output_len += len(g[0].text)
    if self._token_callback:
      try:
        self._token_callback(
          self.manager_name,
          input_tokens if input_tokens is not None else 0,
          output_tokens if output_tokens is not None else 0,
        )
      except Exception as e:
        logger.warning("token_callback_failed", error=str(e))
    logger.info(
      "llm_call_ended",
      manager=self.manager_name,
      call_number=self._llm_call_count,
      run_id=str(run_id),
      output_len=output_len,
      input_tokens=input_tokens,
      output_tokens=output_tokens,
    )

  def on_llm_error(
    self,
    error: BaseException,
    *,
    run_id: UUID,
    parent_run_id: Optional[UUID] = None,
    **kwargs: Any,
  ) -> None:
    logger.error(
      "llm_call_error",
      manager=self.manager_name,
      run_id=str(run_id),
      error=str(error),
    )

  def on_tool_start(
    self,
    serialized: Dict[str, Any],
    input_str: str,
    *,
    run_id: UUID,
    parent_run_id: Optional[UUID] = None,
    **kwargs: Any,
  ) -> None:
    self._tool_call_count += 1
    tool_name = serialized.get("name", "unknown")
    logger.info(
      "tool_started",
      manager=self.manager_name,
      tool=tool_name,
      call_number=self._tool_call_count,
      run_id=str(run_id),
      input_preview=(input_str[:150] + "...") if len(input_str) > 150 else input_str,
    )

  def on_tool_end(
    self,
    output: Any,
    *,
    run_id: UUID,
    parent_run_id: Optional[UUID] = None,
    **kwargs: Any,
  ) -> None:
    out_str = _content_to_str(output)
    logger.info(
      "tool_ended",
      manager=self.manager_name,
      call_number=self._tool_call_count,
      run_id=str(run_id),
      output_len=len(out_str),
      output_preview=(out_str[:120] + "...") if len(out_str) > 120 else out_str,
    )

  def on_tool_error(
    self,
    error: BaseException,
    *,
    run_id: UUID,
    parent_run_id: Optional[UUID] = None,
    **kwargs: Any,
  ) -> None:
    logger.error(
      "tool_error",
      manager=self.manager_name,
      run_id=str(run_id),
      error=str(error),
    )
