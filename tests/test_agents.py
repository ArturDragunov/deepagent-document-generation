"""Tests for agent definitions."""

import pytest
from unittest.mock import patch, MagicMock

from src.prompts.prompt_library import PromptLibrary


class TestPromptLibrary:
  """Test prompt library methods."""

  def test_subagent_descriptions_exist(self):
    """All domain+type combos should return non-empty descriptions."""
    domains = ["drool", "model", "outbound", "transformation", "inbound", "reviewer"]
    types = ["analysis", "synthesis", "writer", "review"]

    for domain in domains:
      for sub_type in types:
        desc = PromptLibrary.get_subagent_description(domain, sub_type)
        assert desc, f"Missing description for {domain}/{sub_type}"
        assert len(desc) > 5

  def test_file_filter_description(self):
    desc = PromptLibrary.get_subagent_description("drool", "file_filter")
    assert "file" in desc.lower() or "filter" in desc.lower()

  def test_subagent_prompts_exist(self):
    """All subagent prompts should return non-empty strings."""
    domains = ["drool", "model", "outbound", "transformation", "inbound"]
    types = ["analysis", "synthesis", "writer", "review"]

    for domain in domains:
      for sub_type in types:
        prompt = PromptLibrary.get_subagent_prompt(domain, sub_type)
        assert prompt, f"Missing prompt for {domain}/{sub_type}"
        assert len(prompt) > 20

  def test_file_filter_prompt(self):
    prompt = PromptLibrary.get_subagent_prompt("drool", "file_filter")
    assert "filter" in prompt.lower() or "relevant" in prompt.lower()
    assert "JSON" in prompt

  def test_manager_prompts_exist(self):
    """All manager prompts should exist and be non-empty."""
    prompts = [
      PromptLibrary.get_drool_manager_prompt(),
      PromptLibrary.get_model_manager_prompt(),
      PromptLibrary.get_outbound_manager_prompt(),
      PromptLibrary.get_transformation_manager_prompt(),
      PromptLibrary.get_inbound_manager_prompt(),
      PromptLibrary.get_reviewer_supervisor_prompt(),
    ]
    for p in prompts:
      assert p
      assert len(p) > 50

  def test_reviewer_prompt_mentions_execute_python(self):
    prompt = PromptLibrary.get_reviewer_supervisor_prompt()
    assert "execute_python" in prompt
    assert "docx" in prompt.lower() or ".docx" in prompt

  def test_reviewer_prompt_mentions_brd_sections(self):
    prompt = PromptLibrary.get_reviewer_supervisor_prompt()
    assert "Executive Summary" in prompt
    assert "Requirements" in prompt
    assert "Data Models" in prompt


class TestAgentDefinitions:
  """Test agent factory functions (without actually calling deepagents)."""

  @patch("src.agents.agent_definitions.create_deep_agent")
  def test_create_all_managers(self, mock_create):
    """All 6 managers should be created."""
    mock_create.return_value = MagicMock()

    from src.agents.agent_definitions import create_all_managers
    managers = create_all_managers(model="openai:gpt-4")

    assert len(managers) == 6
    assert set(managers.keys()) == {
      "drool", "model", "outbound", "transformation", "inbound", "reviewer",
    }
    assert mock_create.call_count == 6

  @patch("src.agents.agent_definitions.create_deep_agent")
  def test_drool_has_5_subagents(self, mock_create):
    """Drool should have 5 sub-agents (file_filter + 4 standard)."""
    mock_create.return_value = MagicMock()

    from src.agents.agent_definitions import create_drool_manager
    create_drool_manager(model="openai:gpt-4")

    call_kwargs = mock_create.call_args
    subagents = call_kwargs.kwargs.get("subagents", [])
    assert len(subagents) == 5

  @patch("src.agents.agent_definitions.create_deep_agent")
  def test_reviewer_has_execute_python(self, mock_create):
    """Reviewer should have execute_python in its tools."""
    mock_create.return_value = MagicMock()

    from src.agents.agent_definitions import create_reviewer_supervisor
    create_reviewer_supervisor(model="openai:gpt-4")

    call_kwargs = mock_create.call_args
    tools = call_kwargs.kwargs.get("tools", [])
    tool_names = [t.__name__ for t in tools]
    assert "execute_python" in tool_names

  @patch("src.agents.agent_definitions.create_deep_agent")
  def test_model_provider_passed(self, mock_create):
    """model_provider should be passed to create_deep_agent when provided."""
    mock_create.return_value = MagicMock()

    from src.agents.agent_definitions import create_model_manager
    create_model_manager(model="anthropic.claude-3", model_provider="bedrock_converse")

    call_kwargs = mock_create.call_args
    assert call_kwargs.kwargs.get("model_provider") == "bedrock_converse"
