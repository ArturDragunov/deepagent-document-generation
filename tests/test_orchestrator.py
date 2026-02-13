"""Tests for orchestrator and guardrails."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.orchestrator import BRDOrchestrator
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

  def test_config_defaults(self):
    from src.config import reset_config, get_config
    reset_config()
    config = get_config()
    assert config.llm_model == "openai:gpt-4"
    assert config.agent_timeout_sec == 300
    assert config.max_retries == 2

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
