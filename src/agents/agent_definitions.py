"""Agent definitions using deepagents native subagent support.

This module creates manager agents with specialized sub-agents, following deepagents best practices.
Each manager has sub-agents for Analysis, Synthesis, Writing, and Review phases.

Sub-agents are defined as dictionaries and passed directly to create_deep_agent(),
which handles their orchestration and invocation.
"""

from typing import Callable, List, Any, Optional, Dict
from deepagents import create_deep_agent
from langchain.chat_models import BaseChatModel

from src.prompts.prompt_library import PromptLibrary
from src.tools.file_reader import read_file, list_corpus_files
from src.tools.regex_tool import (
    search_files_by_pattern,
    match_patterns_in_text,
    extract_keywords,
)
from src.tools.token_estimator import estimate_tokens_in_text, calculate_cost


# ============================================================================
# Sub-Agent Factory Functions
# ============================================================================


def create_sub_agent_dict(
    domain: str,
    sub_type: str,
    tools: Optional[List[Callable]] = None,
) -> Dict[str, Any]:
    """Create a subagent dictionary for deepagents.

    Args:
        domain: Domain name (e.g., 'drool', 'model', 'outbound')
        sub_type: Sub-agent type ('analysis', 'synthesis', 'writer', 'review')
        tools: Optional list of tools for this sub-agent

    Returns:
        Dictionary configured for deepagents subagents parameter
    """
    if tools is None:
        tools = []

    return {
        "name": f"{domain}_{sub_type}",
        "description": PromptLibrary.get_subagent_description(domain, sub_type),
        "system_prompt": PromptLibrary.get_subagent_prompt(domain, sub_type),
        "tools": tools,
    }


# ============================================================================
# Manager Agent Factory Functions
# ============================================================================


def create_drool_manager(
    model: BaseChatModel,
    tools: Optional[List[Callable]] = None,
) -> Any:
    """Create Drool Manager Agent with specialized sub-agents.

    The Drool Manager orchestrates sub-agents for:
    1. File Filter: Identify relevant files using patterns
    2. Analysis: Extract key requirements from files
    3. Synthesis: Consolidate and reconcile findings
    4. Writer: Generate professional specification
    5. Review: Validate completeness and quality

    Args:
        model: LLM chat model
        tools: Optional tool overrides

    Returns:
        deepagents Agent instance with sub-agents
    """
    if tools is None:
        tools = [
            read_file,
            list_corpus_files,
            search_files_by_pattern,
            match_patterns_in_text,
            extract_keywords,
        ]

    # Define sub-agents as dictionaries
    subagents = [
        create_sub_agent_dict(
            "drool",
            "file_filter",
            tools=[
                search_files_by_pattern,
                match_patterns_in_text,
                extract_keywords,
                read_file,
                list_corpus_files,
            ],
        ),
        create_sub_agent_dict(
            "drool",
            "analysis",
            tools=[read_file, list_corpus_files],
        ),
        create_sub_agent_dict("drool", "synthesis", tools=[]),
        create_sub_agent_dict("drool", "writer", tools=[]),
        create_sub_agent_dict("drool", "review", tools=[]),
    ]

    agent = create_deep_agent(
        model=model,
        tools=tools,
        system_prompt=PromptLibrary.get_drool_manager_prompt(),
        subagents=subagents,
    )
    return agent


def create_model_manager(
    model: BaseChatModel,
    tools: Optional[List[Callable]] = None,
) -> Any:
    """Create Model Manager Agent with specialized sub-agents.

    Orchestrates sub-agents for data model extraction and documentation:
    1. Analysis: Extract entities, attributes, relationships
    2. Synthesis: Consolidate into unified data model
    3. Writer: Generate professional data model specification
    4. Review: Validate completeness

    Args:
        model: LLM chat model
        tools: Optional tool overrides

    Returns:
        deepagents Agent instance with sub-agents
    """
    if tools is None:
        tools = [read_file, list_corpus_files]

    subagents = [
        create_sub_agent_dict("model", "analysis", tools=[read_file, list_corpus_files]),
        create_sub_agent_dict("model", "synthesis", tools=[]),
        create_sub_agent_dict("model", "writer", tools=[]),
        create_sub_agent_dict("model", "review", tools=[]),
    ]

    agent = create_deep_agent(
        model=model,
        tools=tools,
        system_prompt=PromptLibrary.get_model_manager_prompt(),
        subagents=subagents,
    )
    return agent


def create_outbound_manager(
    model: BaseChatModel,
    tools: Optional[List[Callable]] = None,
) -> Any:
    """Create Outbound Manager Agent with specialized sub-agents.

    Orchestrates sub-agents for outbound integration analysis:
    1. Analysis: Extract API endpoints and external integrations
    2. Synthesis: Consolidate integration patterns
    3. Writer: Generate outbound integration specification
    4. Review: Validate API specifications

    Args:
        model: LLM chat model
        tools: Optional tool overrides

    Returns:
        deepagents Agent instance with sub-agents
    """
    if tools is None:
        tools = [read_file, list_corpus_files]

    subagents = [
        create_sub_agent_dict(
            "outbound", "analysis", tools=[read_file, list_corpus_files]
        ),
        create_sub_agent_dict("outbound", "synthesis", tools=[]),
        create_sub_agent_dict("outbound", "writer", tools=[]),
        create_sub_agent_dict("outbound", "review", tools=[]),
    ]

    agent = create_deep_agent(
        model=model,
        tools=tools,
        system_prompt=PromptLibrary.get_outbound_manager_prompt(),
        subagents=subagents,
    )
    return agent


def create_transformation_manager(
    model: BaseChatModel,
    tools: Optional[List[Callable]] = None,
) -> Any:
    """Create Transformation Manager Agent with specialized sub-agents.

    Orchestrates sub-agents for data transformation analysis:
    1. Analysis: Extract transformation rules and mappings
    2. Synthesis: Consolidate transformation logic
    3. Writer: Generate transformation specification
    4. Review: Validate transformation completeness

    Args:
        model: LLM chat model
        tools: Optional tool overrides

    Returns:
        deepagents Agent instance with sub-agents
    """
    if tools is None:
        tools = [read_file, list_corpus_files]

    subagents = [
        create_sub_agent_dict(
            "transformation", "analysis", tools=[read_file, list_corpus_files]
        ),
        create_sub_agent_dict("transformation", "synthesis", tools=[]),
        create_sub_agent_dict("transformation", "writer", tools=[]),
        create_sub_agent_dict("transformation", "review", tools=[]),
    ]

    agent = create_deep_agent(
        model=model,
        tools=tools,
        system_prompt=PromptLibrary.get_transformation_manager_prompt(),
        subagents=subagents,
    )
    return agent


def create_inbound_manager(
    model: BaseChatModel,
    tools: Optional[List[Callable]] = None,
) -> Any:
    """Create Inbound Manager Agent with specialized sub-agents.

    Orchestrates sub-agents for inbound data integration analysis:
    1. Analysis: Extract data sources and ingestion requirements
    2. Synthesis: Consolidate inbound integration patterns
    3. Writer: Generate inbound integration specification
    4. Review: Validate data quality and ingestion logic

    Args:
        model: LLM chat model
        tools: Optional tool overrides

    Returns:
        deepagents Agent instance with sub-agents
    """
    if tools is None:
        tools = [read_file, list_corpus_files]

    subagents = [
        create_sub_agent_dict("inbound", "analysis", tools=[read_file, list_corpus_files]),
        create_sub_agent_dict("inbound", "synthesis", tools=[]),
        create_sub_agent_dict("inbound", "writer", tools=[]),
        create_sub_agent_dict("inbound", "review", tools=[]),
    ]

    agent = create_deep_agent(
        model=model,
        tools=tools,
        system_prompt=PromptLibrary.get_inbound_manager_prompt(),
        subagents=subagents,
    )
    return agent


def create_reviewer_supervisor(
    model: BaseChatModel,
    tools: Optional[List[Callable]] = None,
) -> Any:
    """Create Reviewer/Supervisor Agent with specialized sub-agents.

    Final authority for BRD quality and completeness. Orchestrates:
    1. Writer: Synthesize all manager outputs into final BRD
    2. Review: Validate completeness and detect gaps

    This agent can request managers to reprocess sections if gaps detected.

    Args:
        model: LLM chat model
        tools: Optional tool overrides

    Returns:
        deepagents Agent instance with sub-agents
    """
    if tools is None:
        tools = [estimate_tokens_in_text, calculate_cost]

    subagents = [
        create_sub_agent_dict("reviewer", "writer", tools=[]),
        create_sub_agent_dict("reviewer", "review", tools=[]),
    ]

    agent = create_deep_agent(
        model=model,
        tools=tools,
        system_prompt=PromptLibrary.get_reviewer_supervisor_prompt(),
        subagents=subagents,
    )
    return agent


# ============================================================================
# Convenience Functions
# ============================================================================


def create_all_managers(model: BaseChatModel) -> Dict[str, Any]:
    """Create all 6 manager agents with their sub-agents.

    Args:
        model: LLM chat model for all agents

    Returns:
        Dictionary mapping manager names to agent instances
    """
    return {
        "drool": create_drool_manager(model),
        "model": create_model_manager(model),
        "outbound": create_outbound_manager(model),
        "transformation": create_transformation_manager(model),
        "inbound": create_inbound_manager(model),
        "reviewer": create_reviewer_supervisor(model),
    }
