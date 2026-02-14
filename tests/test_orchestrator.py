"""Tests for orchestrator and guardrails."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.orchestrator import BRDOrchestrator, group_files_by_workbook
from src.models import MessageStatus


class TestInputGuardrail:
  """Test input guardrail validation."""

  def test_empty_query(self):
    from src.guardrails import get_input_guardrail
    guardrail = get_input_guardrail()
    is_valid, violations = guardrail.validate_input("")
    assert not is_valid

  def test_valid_query(self):
    from src.guardrails import get_input_guardrail
    guardrail = get_input_guardrail()
    is_valid, violations = guardrail.validate_input("Create BRD for LC0070 system")
    assert is_valid
    assert len(violations) == 0

  def test_too_short_query(self):
    from src.guardrails import get_input_guardrail
    guardrail = get_input_guardrail()
    is_valid, violations = guardrail.validate_input("hi")
    assert not is_valid

  def test_content_moderation(self):
    from src.guardrails import get_input_guardrail
    guardrail = get_input_guardrail()
    is_valid, violations = guardrail.validate_input("instructions for bomb making explosive recipe")
    assert not is_valid
    assert any("Dangerous" in v.message for v in violations)


class TestConfiguration:
  """Test configuration management."""

  def test_config_singleton(self):
    from src.config import get_config, reset_config
    config1 = get_config()
    config2 = get_config()
    assert config1 is config2

    reset_config()
    config3 = get_config()
    assert config3 is not config1

  def test_config_env_override(self, monkeypatch):
    from src.config import reset_config, get_config
    reset_config()
    monkeypatch.setenv("LLM_MODEL", "openai:gpt-3.5-turbo")
    monkeypatch.setenv("AGENT_TIMEOUT_SEC", "120")
    config = get_config()
    assert config.llm_model == "openai:gpt-3.5-turbo"
    assert config.agent_timeout_sec == 120

  def test_config_model_provider(self, monkeypatch):
    from src.config import reset_config, get_config
    reset_config()
    monkeypatch.setenv("LLM_MODEL_PROVIDER", "bedrock_converse")
    config = get_config()
    assert config.llm_model_provider == "bedrock_converse"

  def test_reviewer_timeout_sec(self, monkeypatch):
    from src.config import reset_config, get_config
    reset_config()
    monkeypatch.setenv("REVIEWER_TIMEOUT_SEC", "900")
    config = get_config()
    assert config.reviewer_timeout_sec == 900


@pytest.mark.asyncio
class TestBRDOrchestrator:
  """Test BRDOrchestrator pipeline."""

  async def test_invalid_input_returns_error(self, monkeypatch):
    """Empty query should fail validation."""
    monkeypatch.setenv("LLM_MODEL", "openai:gpt-4")
    from src.config import reset_config
    reset_config()

    orchestrator = BRDOrchestrator()
    result = await orchestrator.run_pipeline(
      user_query="",
      corpus_files=[],
    )
    assert result.status == MessageStatus.ERROR
    assert len(result.errors) > 0

  async def test_too_long_query_returns_error(self, monkeypatch):
    """Very long query should fail validation."""
    monkeypatch.setenv("LLM_MODEL", "openai:gpt-4")
    from src.config import reset_config
    reset_config()

    orchestrator = BRDOrchestrator()
    result = await orchestrator.run_pipeline(
      user_query="test " * 2000,
      corpus_files=[],
    )
    assert result.status == MessageStatus.ERROR


class TestGroupFilesByWorkbook:
  """Test file grouping for workbook-scoped runs."""

  def test_empty_returns_empty(self):
    assert group_files_by_workbook([], "_sheet") == []

  def test_no_delimiter_each_file_own_group(self):
    files = ["a.jsonl", "b.jsonl"]
    assert group_files_by_workbook(files, "_sheet") == [["a.jsonl"], ["b.jsonl"]]

  def test_same_prefix_one_group(self):
    files = ["workbook_A_sheet1.jsonl", "workbook_A_sheet2.jsonl"]
    got = group_files_by_workbook(files, "_sheet")
    assert len(got) == 1
    assert set(got[0]) == set(files)

  def test_two_workbooks_two_groups(self):
    files = [
      "workbook_A_sheet1.jsonl",
      "workbook_A_sheet2.jsonl",
      "workbook_B_sheet1.jsonl",
    ]
    got = group_files_by_workbook(files, "_sheet")
    assert len(got) == 2
    assert set(got[0]) == {"workbook_A_sheet1.jsonl", "workbook_A_sheet2.jsonl"}
    assert got[1] == ["workbook_B_sheet1.jsonl"]

  def test_max_per_group_splits_large_workbook(self):
    files = [f"workbook_A_sheet{i}.jsonl" for i in range(20)]
    got = group_files_by_workbook(files, "_sheet", max_per_group=8)
    assert len(got) == 3
    assert len(got[0]) == 8
    assert len(got[1]) == 8
    assert len(got[2]) == 4


@pytest.mark.asyncio
async def test_run_pipeline_success_with_mocked_managers(test_output_dir, monkeypatch):
  """Full pipeline run with mocked LLM agents (no real API calls)."""
  monkeypatch.setenv("LLM_MODEL", "openai:gpt-4")
  monkeypatch.setenv("OUTPUT_DIR", str(test_output_dir))
  from src.config import reset_config
  reset_config()

  from src.models import MessageStatus
  from src.orchestrator import BRDOrchestrator

  mock_invoke_result = {"messages": [MagicMock(content="# BRD section")]}
  mock_agent = MagicMock()
  mock_agent.ainvoke = AsyncMock(return_value=mock_invoke_result)
  mock_managers = {
    "drool": mock_agent,
    "model": mock_agent,
    "outbound": mock_agent,
    "transformation": mock_agent,
    "inbound": mock_agent,
    "reviewer": mock_agent,
  }

  with patch.object(BRDOrchestrator, "_filter_drool_files", new_callable=AsyncMock, return_value=[]):
    with patch("src.orchestrator.create_all_managers", return_value=mock_managers):
      orchestrator = BRDOrchestrator()
      result = await orchestrator.run_pipeline(
        user_query="Create BRD for LC0070 payment auth",
        corpus_files=["Outbound/spec.md", "Transformation/mappings.jsonl"],
      )

  assert result.status == MessageStatus.SUCCESS
  assert result.execution_id
  assert len(result.all_messages) >= 1
