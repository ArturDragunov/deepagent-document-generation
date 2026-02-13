"""Pytest configuration and fixtures."""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.config import reset_config, get_config
from src.guardrails import reset_input_guardrail


@pytest.fixture(scope="session")
def event_loop():
  """Create an event loop for the test session."""
  loop = asyncio.get_event_loop_policy().new_event_loop()
  yield loop
  loop.close()


@pytest.fixture(autouse=True)
def reset_singletons():
  """Reset singletons before each test."""
  reset_config()
  reset_input_guardrail()
  yield


@pytest.fixture
def test_config(monkeypatch):
  """Config with test-friendly defaults."""
  monkeypatch.setenv("LLM_MODEL", "openai:gpt-4")
  monkeypatch.setenv("CORPUS_DIR", "example_data/corpus")
  monkeypatch.setenv("OUTPUT_DIR", "outputs")
  return get_config()


@pytest.fixture
def test_corpus_dir(tmp_path):
  """Temporary corpus directory with sample files."""
  corpus = tmp_path / "corpus"
  corpus.mkdir()

  (corpus / "test.jsonl").write_text(
    '{"id": "1", "content": "test content"}\n'
    '{"id": "2", "content": "more test content"}\n'
  )
  (corpus / "test.md").write_text("# Test\n\nTest markdown content")
  (corpus / "test.txt").write_text("Plain text content")
  (corpus / "test.drl").write_text(
    'rule "test_rule"\n  when\n    $order : Order()\n  then\n    // action\nend\n'
  )

  return corpus


@pytest.fixture
def test_output_dir(tmp_path):
  """Temporary output directory."""
  output = tmp_path / "outputs"
  output.mkdir()
  return output
