"""Tests for drool file filter."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from src.tools.drool_filter import filter_drool_files, FileRelevance


@pytest.mark.asyncio
async def test_filter_empty_paths():
  result = await filter_drool_files("query", [])
  assert result == {"included": [], "excluded": []}


@pytest.mark.asyncio
async def test_filter_include_exclude(test_corpus_dir, monkeypatch):
  monkeypatch.setenv("CORPUS_DIR", str(test_corpus_dir))
  from src.config import reset_config
  reset_config()

  mock_llm = MagicMock()
  mock_llm.ainvoke = AsyncMock(side_effect=[
    FileRelevance(include=True, reason="relevant"),
    FileRelevance(include=False, reason="not relevant"),
  ])
  mock_llm.with_structured_output = MagicMock(return_value=mock_llm)

  with patch("src.tools.drool_filter.get_chat_model", return_value=mock_llm):
    result = await filter_drool_files("BRD for LC0070", ["test.drl", "test.md"])

  assert set(result["included"]) == {"test.drl"}
  assert set(result["excluded"]) == {"test.md"}
  assert mock_llm.ainvoke.call_count == 2


@pytest.mark.asyncio
async def test_filter_error_conservative_include(test_corpus_dir, monkeypatch):
  monkeypatch.setenv("CORPUS_DIR", str(test_corpus_dir))
  from src.config import reset_config
  reset_config()

  mock_llm = MagicMock()
  mock_llm.ainvoke = AsyncMock(side_effect=RuntimeError("API error"))
  mock_llm.with_structured_output = MagicMock(return_value=mock_llm)

  with patch("src.tools.drool_filter.get_chat_model", return_value=mock_llm):
    result = await filter_drool_files("query", ["test.drl"])

  assert result["included"] == ["test.drl"]
  assert result["excluded"] == []
