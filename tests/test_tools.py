"""Tests for tool functions."""

import pytest
from pathlib import Path

from src.tools.corpus_reader import read_corpus_file
from src.tools.token_estimator import estimate_tokens, calculate_cost
from src.tools.code_executor import execute_python


class TestCorpusReader:
  """Test read_corpus_file."""

  def test_read_jsonl(self, test_corpus_dir, monkeypatch):
    monkeypatch.setenv("CORPUS_DIR", str(test_corpus_dir))
    from src.config import reset_config
    reset_config()

    result = read_corpus_file("test.jsonl")
    assert "JSONL File" in result
    assert "test content" in result or "id" in result

  def test_read_markdown(self, test_corpus_dir, monkeypatch):
    monkeypatch.setenv("CORPUS_DIR", str(test_corpus_dir))
    from src.config import reset_config
    reset_config()

    result = read_corpus_file("test.md")
    assert "# Test" in result

  def test_read_text(self, test_corpus_dir, monkeypatch):
    monkeypatch.setenv("CORPUS_DIR", str(test_corpus_dir))
    from src.config import reset_config
    reset_config()

    result = read_corpus_file("test.txt")
    assert "Plain text content" in result

  def test_read_drl(self, test_corpus_dir, monkeypatch):
    monkeypatch.setenv("CORPUS_DIR", str(test_corpus_dir))
    from src.config import reset_config
    reset_config()

    result = read_corpus_file("test.drl")
    assert "rule" in result
    assert "test_rule" in result

  def test_read_nonexistent(self, test_corpus_dir, monkeypatch):
    monkeypatch.setenv("CORPUS_DIR", str(test_corpus_dir))
    from src.config import reset_config
    reset_config()

    result = read_corpus_file("nonexistent.txt")
    assert "ERROR" in result
    assert "not found" in result


class TestTokenEstimator:
  """Test estimate_tokens and calculate_cost."""

  def test_estimate_tokens(self, monkeypatch):
    monkeypatch.setenv("INPUT_COST_PER_1K", "0.003")
    from src.config import reset_config
    reset_config()

    result = estimate_tokens("This is a test string for token estimation.")
    assert "Tokens:" in result
    assert "cost" in result.lower()

  def test_calculate_cost(self, monkeypatch):
    monkeypatch.setenv("INPUT_COST_PER_1K", "0.003")
    monkeypatch.setenv("OUTPUT_COST_PER_1K", "0.006")
    from src.config import reset_config
    reset_config()

    result = calculate_cost(input_tokens=1000, output_tokens=500)
    assert "Input:" in result
    assert "Output:" in result
    assert "Total:" in result


class TestCodeExecutor:
  """Test execute_python."""

  def test_execute_simple(self):
    result = execute_python("print('hello world')")
    assert "hello world" in result
    assert "EXIT CODE: 0" in result

  def test_execute_error(self):
    result = execute_python("raise ValueError('test error')")
    assert "test error" in result or "ValueError" in result

  def test_execute_timeout(self):
    result = execute_python("import time; time.sleep(10)", timeout_sec=1)
    assert "timed out" in result.lower() or "ERROR" in result
