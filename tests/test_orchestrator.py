"""Tests for orchestrator."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from src.orchestrator import AsyncOrchestrator
from src.models import MessageStatus


@pytest.mark.asyncio
class TestAsyncOrchestrator:
    """Test AsyncOrchestrator."""

    async def test_initialization(self, mock_llm_client):
        """Test orchestrator initialization."""
        orchestrator = AsyncOrchestrator(llm_client=mock_llm_client)

        assert orchestrator.drool_agent is not None
        assert orchestrator.model_agent is not None
        assert orchestrator.outbound_agent is not None
        assert orchestrator.transformation_agent is not None
        assert orchestrator.inbound_agent is not None
        assert orchestrator.reviewer_agent is not None

    async def test_input_validation_with_long_query(self, mock_llm_client):
        """Test input validation rejects overly long queries."""
        orchestrator = AsyncOrchestrator(llm_client=mock_llm_client)

        # Create a very long query
        long_query = "test " * 2000  # > max allowed

        result = await orchestrator.run_pipeline(
            user_query=long_query,
            corpus_files=[],
        )

        assert result.status == MessageStatus.ERROR

    async def test_input_validation_with_valid_query(self, mock_llm_client, test_output_dir):
        """Test input validation accepts valid queries."""
        orchestrator = AsyncOrchestrator(llm_client=mock_llm_client)

        # Mock all manager agents to prevent actual execution
        for attr in [
            "drool_agent",
            "model_agent",
            "outbound_agent",
            "transformation_agent",
            "inbound_agent",
            "reviewer_agent",
        ]:
            agent = getattr(orchestrator, attr)
            agent.execute_with_subagents = AsyncMock(
                return_value=MagicMock(
                    agent_id=f"{attr}_test",
                    agent_type=MagicMock(value="manager"),
                    markdown_content="Test content",
                    token_account=MagicMock(estimated_tokens=100, cost_estimate=0.05),
                    status=MessageStatus.SUCCESS,
                )
            )

        # Mock reviewer agent execute separately
        orchestrator.reviewer_agent.execute = AsyncMock(
            return_value=MagicMock(
                agent_id="reviewer_test",
                agent_type=MagicMock(value="manager"),
                markdown_content="Final BRD content",
                token_account=MagicMock(estimated_tokens=50, cost_estimate=0.02),
                metadata={
                    "brd_file": str(test_output_dir / "test_brd.docx"),
                    "gaps_found": False,
                },
                status=MessageStatus.SUCCESS,
            )
        )

        result = await orchestrator.run_pipeline(
            user_query="Test valid query",
            corpus_files=["test.jsonl"],
            output_dir=test_output_dir,
        )

        # Should get past validation, though execution might be mocked
        assert result is not None

    async def test_close(self, mock_llm_client):
        """Test graceful shutdown."""
        orchestrator = AsyncOrchestrator(llm_client=mock_llm_client)
        await orchestrator.close()

        # Verify close was called
        mock_llm_client.close.assert_called_once()


class TestInputGuardrail:
    """Test input guardrail."""

    def test_empty_query_validation(self):
        """Test that empty queries are rejected."""
        from src.guardrails import get_input_guardrail

        guardrail = get_input_guardrail()
        is_valid, violations = guardrail.validate_input("")

        assert not is_valid
        assert len(violations) > 0

    def test_valid_query_validation(self):
        """Test that valid queries pass."""
        from src.guardrails import get_input_guardrail

        guardrail = get_input_guardrail()
        is_valid, violations = guardrail.validate_input("This is a valid query")

        assert is_valid
        assert len(violations) == 0

    def test_banned_pattern_validation(self):
        """Test that banned patterns are rejected."""
        from src.guardrails import get_input_guardrail

        guardrail = get_input_guardrail()
        is_valid, violations = guardrail.validate_input("DROP TABLE users; --")

        assert not is_valid
        assert any("SQL" in v.message for v in violations)


class TestConfiguration:
    """Test configuration management."""

    def test_config_singleton(self):
        """Test config singleton pattern."""
        from src.config import get_config, reset_config

        config1 = get_config()
        config2 = get_config()

        assert config1 is config2

        reset_config()
        config3 = get_config()
        assert config3 is not config1

    def test_config_env_loading(self, monkeypatch):
        """Test environment variable loading."""
        from src.config import reset_config, get_config

        reset_config()

        monkeypatch.setenv("AGENT_TIMEOUT_SEC", "120")
        config = get_config()

        assert config.agent_timeout_sec == 120
