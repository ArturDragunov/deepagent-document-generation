"""Agent definitions using deepagents -- simplified flat agents (no sub-agents).

Each manager is a single deepagents agent with:
- Sync tool functions (framework handles async)
- Model specified as string ("openai:gpt-4") -- no BaseChatModel needed
- Default StateBackend (ephemeral) -- NO FilesystemBackend (restricts disk access)
- Agents read corpus files ONLY through read_corpus_file tool
- Built-in tools (write_todos, read_todos) still available for planning
"""

from typing import Any, Dict, Optional

from deepagents import create_deep_agent

from src.prompts.prompt_library import PromptLibrary
from src.tools.corpus_reader import read_corpus_file
from src.tools.agent_output import read_agent_output, list_agent_outputs
from src.tools.token_estimator import estimate_tokens, calculate_cost
from src.tools.code_executor import execute_python


# ============================================================================
# Manager Agent Factories
# ============================================================================

def create_drool_manager(
  model: str,
  model_provider: Optional[str] = None,
) -> Any:
  """Create Drool Manager -- flat agent, no sub-agents.

  Reads pre-filtered drool files, extracts business rules and requirements.
  File filtering is done upstream by the orchestrator (LLM-based filter).
  """
  kwargs = _model_kwargs(model, model_provider)

  return create_deep_agent(
    **kwargs,
    tools=[read_corpus_file, read_agent_output, list_agent_outputs],
    system_prompt=PromptLibrary.get_drool_manager_prompt(),
  )


def create_model_manager(
  model: str,
  model_provider: Optional[str] = None,
) -> Any:
  """Create Model Manager -- flat agent, no sub-agents.

  Parses JSON/JSONL model specs and extracts structured model information.
  """
  kwargs = _model_kwargs(model, model_provider)

  return create_deep_agent(
    **kwargs,
    tools=[read_corpus_file, read_agent_output, list_agent_outputs],
    system_prompt=PromptLibrary.get_model_manager_prompt(),
  )


def create_outbound_manager(
  model: str,
  model_provider: Optional[str] = None,
) -> Any:
  """Create Outbound Manager -- flat agent, no sub-agents.

  Processes workbook JSONL sheets for outbound integration data.
  """
  kwargs = _model_kwargs(model, model_provider)

  return create_deep_agent(
    **kwargs,
    tools=[read_corpus_file, read_agent_output, list_agent_outputs],
    system_prompt=PromptLibrary.get_outbound_manager_prompt(),
  )


def create_transformation_manager(
  model: str,
  model_provider: Optional[str] = None,
) -> Any:
  """Create Transformation Manager -- flat agent, no sub-agents.

  Processes transformation rules, mappings, and validation logic.
  """
  kwargs = _model_kwargs(model, model_provider)

  return create_deep_agent(
    **kwargs,
    tools=[read_corpus_file, read_agent_output, list_agent_outputs],
    system_prompt=PromptLibrary.get_transformation_manager_prompt(),
  )


def create_inbound_manager(
  model: str,
  model_provider: Optional[str] = None,
) -> Any:
  """Create Inbound Manager -- flat agent, no sub-agents.

  Processes inbound data sources and ingestion requirements.
  """
  kwargs = _model_kwargs(model, model_provider)

  return create_deep_agent(
    **kwargs,
    tools=[read_corpus_file, read_agent_output, list_agent_outputs],
    system_prompt=PromptLibrary.get_inbound_manager_prompt(),
  )


def create_reviewer_supervisor(
  model: str,
  model_provider: Optional[str] = None,
) -> Any:
  """Create Reviewer/Supervisor -- flat agent with code execution for .docx.

  Synthesizes all manager outputs, validates completeness, generates final
  Word document via execute_python tool. If REVIEWER_SYSTEM_PROMPT_PATH exists,
  its content is prepended to the default reviewer prompt.
  """
  from src.config import get_config
  kwargs = _model_kwargs(model, model_provider)
  prompt = PromptLibrary.get_reviewer_supervisor_prompt()
  config = get_config()
  if config.reviewer_system_prompt_path:
    custom = config.reviewer_system_prompt_path.read_text(encoding="utf-8").strip()
    prompt = f"{custom}\n\n{prompt}"
  return create_deep_agent(
    **kwargs,
    tools=[read_corpus_file, read_agent_output, list_agent_outputs, estimate_tokens, calculate_cost, execute_python],
    system_prompt=prompt,
  )


# ============================================================================
# Convenience
# ============================================================================

def create_all_managers(
  model: str,
  model_provider: Optional[str] = None,
) -> Dict[str, Any]:
  """Create all 6 manager agents.

  Args:
      model: Model string (e.g. "openai:gpt-4")
      model_provider: Optional provider override (e.g. "bedrock_converse")

  Returns:
      Dict mapping manager name to agent instance (CompiledStateGraph)
  """
  kwargs = {"model": model, "model_provider": model_provider}
  return {
    "drool": create_drool_manager(**kwargs),
    "model": create_model_manager(**kwargs),
    "outbound": create_outbound_manager(**kwargs),
    "transformation": create_transformation_manager(**kwargs),
    "inbound": create_inbound_manager(**kwargs),
    "reviewer": create_reviewer_supervisor(**kwargs),
  }


# ============================================================================
# Internal helpers
# ============================================================================

def _model_kwargs(model: str, model_provider: Optional[str] = None) -> Dict[str, Any]:
  """Build kwargs dict for create_deep_agent model params."""
  if model_provider:
    return {"model": model, "model_provider": model_provider}
  return {"model": model}
