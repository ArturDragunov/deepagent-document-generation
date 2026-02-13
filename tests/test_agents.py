"""Tests for agents."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.agents.base_agent import BaseAgent
from src.agents.sub_agent import AnalysisSubAgent
from src.agents.manager_agent import ManagerAgent
from src.models import AgentType, ExecutionContext, TokenTracker, MessageStatus


@pytest.mark.asyncio
class TestBaseAgent:
    """Test BaseAgent."""

    async def test_execute_with_timeout(self, mock_llm_client):
        """Test agent execution."""
        agent = BaseAgent(
            agent_id="test_agent",
            agent_type=AgentType.MANAGER,
            timeout_sec=10,
        )

        context = ExecutionContext(
            user_query="Test query",
            corpus_files=[],
            token_tracker=TokenTracker(),
        )

        result = await agent.execute("Test message", context)

        assert result.agent_id == "test_agent"
        assert result.agent_type == AgentType.MANAGER
        assert result.status == MessageStatus.SUCCESS

    async def test_execute_creates_error_message_on_exception(self):
        """Test error message creation."""
        agent = BaseAgent(
            agent_id="test_agent",
            agent_type=AgentType.MANAGER,
        )

        context = ExecutionContext(
            user_query="Test",
            corpus_files=[],
            token_tracker=TokenTracker(),
        )

        # Override _run_agent_logic to raise exception
        async def raise_error(*args, **kwargs):
            raise ValueError("Test error")

        agent._run_agent_logic = raise_error

        result = await agent.execute("Test", context)

        assert result.status == MessageStatus.ERROR
        assert "Test error" in result.markdown_content


@pytest.mark.asyncio
class TestSubAgent:
    """Test SubAgent."""

    async def test_analysis_agent_execution(self, mock_llm_client):
        """Test analysis sub-agent."""
        from src.agents.sub_agent import AnalysisSubAgent

        agent = AnalysisSubAgent(
            agent_id="analysis_1",
            llm_client=mock_llm_client,
            system_prompt="Test prompt",
        )

        context = ExecutionContext(
            user_query="Test",
            corpus_files=[],
            token_tracker=TokenTracker(),
        )

        result = await agent.execute("Test query", context)

        assert result.agent_id == "analysis_1"
        assert result.sub_type.value == "analysis"
        assert result.markdown_content == "# Test Output\n\nMock response from LLM."


@pytest.mark.asyncio
class TestManagerAgent:
    """Test ManagerAgent."""

    async def test_manager_orchestrates_subagents(self, mock_llm_client):
        """Test manager orchestrates sub-agents."""
        prompts = {
            "analysis": "Analysis prompt",
            "synthesis": "Synthesis prompt",
            "writer": "Writer prompt",
            "review": "Review prompt",
        }

        agent = ManagerAgent(
            agent_id="test_manager",
            llm_client=mock_llm_client,
            prompts=prompts,
            timeout_sec=30,
        )

        context = ExecutionContext(
            user_query="Test query",
            corpus_files=[],
            token_tracker=TokenTracker(),
        )

        result = await agent.execute_with_subagents("Test input", context)

        assert result.agent_id == "test_manager"
        assert result.agent_type == AgentType.MANAGER
        assert "## Analysis" in result.markdown_content or "analysis" in result.markdown_content.lower()
        assert result.metadata.get("sub_agents_executed", 0) > 0

    async def test_manager_aggregates_tokens(self, mock_llm_client):
        """Test token aggregation."""
        prompts = {k: f"Prompt {k}" for k in ["analysis", "synthesis", "writer", "review"]}

        agent = ManagerAgent(
            agent_id="test_manager",
            llm_client=mock_llm_client,
            prompts=prompts,
        )

        context = ExecutionContext(
            user_query="Test",
            corpus_files=[],
            token_tracker=TokenTracker(),
        )

        result = await agent.execute_with_subagents("Test", context)

        assert result.token_account is not None
        assert result.token_account.estimated_tokens > 0
        assert result.token_account.cost_estimate > 0
