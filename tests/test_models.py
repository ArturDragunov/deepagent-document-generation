"""Tests for data models."""

import pytest
from pathlib import Path

from src.models import (
  TokenTracker,
  TokenAccount,
  ExecutionContext,
  ExecutionResult,
  MessageStatus,
  AgentType,
  AgentMessage,
)


class TestTokenTracker:
  """Test TokenTracker and TokenAccount."""

  def test_record_and_summary(self):
    tracker = TokenTracker()
    tracker.record_estimate("drool", 100, 50, cost_estimate=0.001)
    tracker.record_estimate("model", 200, 100, cost_estimate=0.002)
    summary = tracker.get_summary()
    assert summary["total_input_tokens"] == 300
    assert summary["total_output_tokens"] == 150
    assert summary["total_estimated_tokens"] == 450
    assert summary["total_cost_estimate"] == 0.003
    assert summary["agent_count"] == 2
    assert len(summary["accounts"]) == 2

  def test_record_zero_tokens(self):
    tracker = TokenTracker()
    tracker.record_estimate("a", 0, 0)
    summary = tracker.get_summary()
    assert summary["total_estimated_tokens"] == 0

  def test_empty_summary(self):
    summary = TokenTracker().get_summary()
    assert summary["total_input_tokens"] == 0
    assert summary["total_output_tokens"] == 0
    assert summary["total_estimated_tokens"] == 0
    assert summary["total_cost_estimate"] == 0
    assert summary["agent_count"] == 0


class TestExecutionContext:
  """Test ExecutionContext."""

  def test_add_message_and_elapsed(self):
    ctx = ExecutionContext(user_query="q", corpus_files=[], output_dir=Path("out"))
    assert len(ctx.all_messages) == 0
    msg = AgentMessage(agent_id="x", agent_type=AgentType.MANAGER, markdown_content="c")
    ctx.add_message(msg)
    assert len(ctx.all_messages) == 1
    assert ctx.get_elapsed_time_sec() >= 0


class TestExecutionResult:
  """Test ExecutionResult."""

  def test_to_dict(self):
    r = ExecutionResult(
      status=MessageStatus.SUCCESS,
      execution_time_sec=12.5,
      execution_id="eid-1",
      warnings=["w1"],
    )
    d = r.to_dict()
    assert d["status"] == "success"
    assert d["execution_time_sec"] == 12.5
    assert d["execution_id"] == "eid-1"
    assert d["warnings"] == ["w1"]
