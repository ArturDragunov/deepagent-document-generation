"""Pytest configuration and fixtures."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain.chat_models import BaseChatModel

from src.config import reset_config, get_config
from src.guardrails import reset_input_guardrail
from src.tools.tool_registry import reset_tool_registry


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton instances before each test."""
    reset_config()
    reset_input_guardrail()
    reset_tool_registry()
    yield


@pytest.fixture
def test_config():
    """Create a test configuration."""
    config = get_config()
    config._env_loaded = False  # Reset
    return config


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client (BaseChatModel for LangChain)."""
    client = MagicMock(spec=BaseChatModel)
    client.invoke = MagicMock(
        return_value=MagicMock(content="# Test Output\n\nMock response from LLM.")
    )
    return client


@pytest.fixture
def test_corpus_dir(tmp_path):
    """Create a temporary corpus directory with sample files."""
    corpus = tmp_path / "corpus"
    corpus.mkdir()

    # Create sample files
    (corpus / "test.jsonl").write_text(
        '{"id": "1", "content": "test content"}\n'
        '{"id": "2", "content": "more test content"}\n'
    )

    (corpus / "test.md").write_text("# Test\n\nTest markdown content")

    (corpus / "test.txt").write_text("Plain text content")

    return corpus


@pytest.fixture
def test_output_dir(tmp_path):
    """Create a temporary output directory."""
    output = tmp_path / "outputs"
    output.mkdir()
    return output
