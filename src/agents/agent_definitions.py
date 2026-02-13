"""Agent definitions using deepagents native subagent support.

Creates manager agents with specialized sub-agents following deepagents best practices:
- Tools are sync plain functions (framework handles async)
- Model specified as string ("openai:gpt-4") or BaseChatModel
- FilesystemBackend for local corpus access
- Built-in tools (ls, glob, grep, read_file, write_file) available automatically
- Custom tools only for format-specific operations
"""

from typing import Any, Callable, Dict, List, Optional

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend

from src.prompts.prompt_library import PromptLibrary
from src.tools.corpus_reader import read_corpus_file
from src.tools.keyword_extractor import extract_keywords
from src.tools.token_estimator import estimate_tokens, calculate_cost
from src.tools.code_executor import execute_python


# ============================================================================
# Sub-Agent Definitions
# ============================================================================

def _subagent(
  domain: str,
  sub_type: str,
  tools: Optional[List[Callable]] = None,
) -> Dict[str, Any]:
  """Create a subagent dict for deepagents.

  Args:
      domain: Domain name ('drool', 'model', 'outbound', etc.)
      sub_type: Sub-agent type ('analysis', 'synthesis', 'writer', 'review', 'file_filter')
      tools: Optional custom tools (built-in tools are always available)
  """
  return {
    "name": f"{domain}_{sub_type}",
    "description": PromptLibrary.get_subagent_description(domain, sub_type),
    "system_prompt": PromptLibrary.get_subagent_prompt(domain, sub_type),
    "tools": tools or [],
  }


# ============================================================================
# Standard sub-agents shared across managers
# ============================================================================

def _standard_subagents(
  domain: str,
  analysis_tools: Optional[List[Callable]] = None,
) -> List[Dict[str, Any]]:
  """Create the 4 standard sub-agents for a manager (Analysis, Synthesis, Writer, Review).

  Args:
      domain: Domain name
      analysis_tools: Extra tools for the analysis sub-agent
  """
  return [
    _subagent(domain, "analysis", tools=analysis_tools or [read_corpus_file]),
    _subagent(domain, "synthesis"),
    _subagent(domain, "writer"),
    _subagent(domain, "review"),
  ]


# ============================================================================
# Manager Agent Factories
# ============================================================================

def create_drool_manager(
  model: str,
  model_provider: Optional[str] = None,
) -> Any:
  """Create Drool Manager with File Filter + standard sub-agents (5 total).

  Sub-agents:
    1. File Filter - regex/keyword-based file identification
    2. Analysis - extract requirements from filtered files
    3. Synthesis - consolidate findings
    4. Writer - generate specification
    5. Review - validate completeness
  """
  subagents = [
    _subagent("drool", "file_filter", tools=[read_corpus_file, extract_keywords]),
    *_standard_subagents("drool", analysis_tools=[read_corpus_file]),
  ]

  kwargs = {"model": model, "model_provider": model_provider} if model_provider else {"model": model}

  return create_deep_agent(
    **kwargs,
    tools=[read_corpus_file, extract_keywords],
    system_prompt=PromptLibrary.get_drool_manager_prompt(),
    subagents=subagents,
    backend=FilesystemBackend(root_dir="."),
  )


def create_model_manager(
  model: str,
  model_provider: Optional[str] = None,
) -> Any:
  """Create Model Manager with standard sub-agents (4 total).

  Parses JSON/JSONL model specs and extracts structured model information.
  """
  kwargs = {"model": model, "model_provider": model_provider} if model_provider else {"model": model}

  return create_deep_agent(
    **kwargs,
    tools=[read_corpus_file],
    system_prompt=PromptLibrary.get_model_manager_prompt(),
    subagents=_standard_subagents("model"),
    backend=FilesystemBackend(root_dir="."),
  )


def create_outbound_manager(
  model: str,
  model_provider: Optional[str] = None,
) -> Any:
  """Create Outbound Manager with standard sub-agents (4 total).

  Processes workbook JSONL sheets for outbound integration data.
  """
  kwargs = {"model": model, "model_provider": model_provider} if model_provider else {"model": model}

  return create_deep_agent(
    **kwargs,
    tools=[read_corpus_file],
    system_prompt=PromptLibrary.get_outbound_manager_prompt(),
    subagents=_standard_subagents("outbound"),
    backend=FilesystemBackend(root_dir="."),
  )


def create_transformation_manager(
  model: str,
  model_provider: Optional[str] = None,
) -> Any:
  """Create Transformation Manager with standard sub-agents (4 total).

  Processes transformation rules, mappings, and validation logic.
  """
  kwargs = {"model": model, "model_provider": model_provider} if model_provider else {"model": model}

  return create_deep_agent(
    **kwargs,
    tools=[read_corpus_file],
    system_prompt=PromptLibrary.get_transformation_manager_prompt(),
    subagents=_standard_subagents("transformation"),
    backend=FilesystemBackend(root_dir="."),
  )


def create_inbound_manager(
  model: str,
  model_provider: Optional[str] = None,
) -> Any:
  """Create Inbound Manager with standard sub-agents (4 total).

  Processes inbound data sources and ingestion requirements.
  """
  kwargs = {"model": model, "model_provider": model_provider} if model_provider else {"model": model}

  return create_deep_agent(
    **kwargs,
    tools=[read_corpus_file],
    system_prompt=PromptLibrary.get_inbound_manager_prompt(),
    subagents=_standard_subagents("inbound"),
    backend=FilesystemBackend(root_dir="."),
  )


def create_reviewer_supervisor(
  model: str,
  model_provider: Optional[str] = None,
) -> Any:
  """Create Reviewer/Supervisor with Writer + Review sub-agents + code execution.

  The reviewer can execute Python code to generate Word documents using python-docx.
  """
  subagents = [
    _subagent("reviewer", "writer"),
    _subagent("reviewer", "review"),
  ]

  kwargs = {"model": model, "model_provider": model_provider} if model_provider else {"model": model}

  return create_deep_agent(
    **kwargs,
    tools=[read_corpus_file, estimate_tokens, calculate_cost, execute_python],
    system_prompt=PromptLibrary.get_reviewer_supervisor_prompt(),
    subagents=subagents,
    backend=FilesystemBackend(root_dir="."),
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
