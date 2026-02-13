"""Tests for agent definitions and prompts."""

import pytest
from unittest.mock import patch, MagicMock

from src.prompts.prompt_library import PromptLibrary


class TestPromptLibrary:
  """Test prompt library methods."""

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

  def test_drool_prompt_no_subagent_references(self):
    """Drool prompt should not reference sub-agents."""
    prompt = PromptLibrary.get_drool_manager_prompt()
    assert "sub-agent" not in prompt.lower()
    assert "delegate" not in prompt.lower()
    assert "read_corpus_file" in prompt

  def test_model_prompt_no_subagent_references(self):
    prompt = PromptLibrary.get_model_manager_prompt()
    assert "sub-agent" not in prompt.lower()
    assert "delegate" not in prompt.lower()

  def test_reviewer_prompt_mentions_execute_python(self):
    prompt = PromptLibrary.get_reviewer_supervisor_prompt()
    assert "execute_python" in prompt
    assert "docx" in prompt.lower() or ".docx" in prompt

  def test_reviewer_prompt_mentions_brd_sections(self):
    prompt = PromptLibrary.get_reviewer_supervisor_prompt()
    assert "Executive Summary" in prompt
    assert "Requirements" in prompt
    assert "Data Models" in prompt

  def test_all_prompts_mention_read_corpus_file(self):
    """All manager prompts should mention the read_corpus_file tool."""
    prompts = [
      PromptLibrary.get_drool_manager_prompt(),
      PromptLibrary.get_model_manager_prompt(),
      PromptLibrary.get_outbound_manager_prompt(),
      PromptLibrary.get_transformation_manager_prompt(),
      PromptLibrary.get_inbound_manager_prompt(),
      PromptLibrary.get_reviewer_supervisor_prompt(),
    ]
    for p in prompts:
      assert "read_corpus_file" in p


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
  def test_no_subagents_passed(self, mock_create):
    """No agent should have subagents parameter."""
    mock_create.return_value = MagicMock()

    from src.agents.agent_definitions import create_all_managers
    create_all_managers(model="openai:gpt-4")

    for call in mock_create.call_args_list:
      assert "subagents" not in call.kwargs, (
        f"subagents should not be passed: {call.kwargs}"
      )

  @patch("src.agents.agent_definitions.create_deep_agent")
  def test_no_filesystem_backend(self, mock_create):
    """No agent should use FilesystemBackend."""
    mock_create.return_value = MagicMock()

    from src.agents.agent_definitions import create_all_managers
    create_all_managers(model="openai:gpt-4")

    for call in mock_create.call_args_list:
      assert "backend" not in call.kwargs, (
        f"backend should not be passed (use default StateBackend): {call.kwargs}"
      )

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

  @patch("src.agents.agent_definitions.create_deep_agent")
  def test_model_provider_not_passed_when_none(self, mock_create):
    """model_provider should NOT be in kwargs when None."""
    mock_create.return_value = MagicMock()

    from src.agents.agent_definitions import create_model_manager
    create_model_manager(model="openai:gpt-4")

    call_kwargs = mock_create.call_args
    assert "model_provider" not in call_kwargs.kwargs
