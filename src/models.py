"""Data models for the BRD generation system."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class AgentType(str, Enum):
  MANAGER = "manager"


class MessageStatus(str, Enum):
  SUCCESS = "success"
  TIMEOUT = "timeout"
  ERROR = "error"
  PARTIAL = "partial"
  FALLBACK = "fallback"


@dataclass
class TokenAccount:
  """Token usage for a single agent execution."""

  agent_id: str
  input_tokens: int = 0
  output_tokens: int = 0
  estimated_tokens: int = 0
  cost_estimate: float = 0.0
  timestamp: datetime = field(default_factory=datetime.now)

  def to_dict(self) -> Dict[str, Any]:
    return {
      "agent_id": self.agent_id,
      "input_tokens": self.input_tokens,
      "output_tokens": self.output_tokens,
      "estimated_tokens": self.estimated_tokens,
      "cost_estimate": round(self.cost_estimate, 6),
      "timestamp": self.timestamp.isoformat(),
    }


@dataclass
class AgentMessage:
  """Structured message from an agent execution."""

  agent_id: str
  agent_type: AgentType
  markdown_content: str = ""
  metadata: Dict[str, Any] = field(default_factory=dict)
  duration_ms: float = 0.0
  token_account: Optional[TokenAccount] = None
  status: MessageStatus = MessageStatus.SUCCESS

  def to_dict(self) -> Dict[str, Any]:
    return {
      "agent_id": self.agent_id,
      "agent_type": self.agent_type.value,
      "markdown_content": self.markdown_content,
      "metadata": self.metadata,
      "duration_ms": round(self.duration_ms, 2),
      "status": self.status.value,
    }


@dataclass
class TokenTracker:
  """Tracks token usage across entire execution."""

  accounts: List[TokenAccount] = field(default_factory=list)

  def record_estimate(
    self,
    agent_id: str,
    input_tokens: int,
    output_tokens: int,
    cost_estimate: Optional[float] = None,
  ) -> None:
    in_t = input_tokens or 0
    out_t = output_tokens or 0
    cost = cost_estimate if cost_estimate is not None else 0.0
    self.accounts.append(TokenAccount(
      agent_id=agent_id,
      input_tokens=in_t,
      output_tokens=out_t,
      estimated_tokens=in_t + out_t,
      cost_estimate=cost,
    ))

  def get_summary(self) -> Dict[str, Any]:
    return {
      "total_input_tokens": sum(a.input_tokens for a in self.accounts),
      "total_output_tokens": sum(a.output_tokens for a in self.accounts),
      "total_estimated_tokens": sum(a.estimated_tokens for a in self.accounts),
      "total_cost_estimate": round(sum(a.cost_estimate for a in self.accounts), 6),
      "agent_count": len(set(a.agent_id for a in self.accounts)),
      "accounts": [a.to_dict() for a in self.accounts],
    }


@dataclass
class ExecutionContext:
  """Shared context for the entire pipeline run."""

  user_query: str
  corpus_files: List[str]
  all_messages: List[AgentMessage] = field(default_factory=list)
  token_tracker: TokenTracker = field(default_factory=TokenTracker)
  output_dir: Path = field(default_factory=lambda: Path("outputs"))
  max_timeout_sec: int = 300
  retry_count: int = 2
  start_time: datetime = field(default_factory=datetime.now)
  execution_id: str = field(default_factory=lambda: datetime.now().isoformat())

  def add_message(self, message: AgentMessage) -> None:
    self.all_messages.append(message)

  def get_elapsed_time_sec(self) -> float:
    return (datetime.now() - self.start_time).total_seconds()


@dataclass
class ReprocessRequest:
  """Request from Reviewer for a manager to reprocess."""

  agent_id: str
  domain: str
  feedback: str
  context: str
  missing_items: List[str] = field(default_factory=list)
  retry_count: int = 0


@dataclass
class ExecutionResult:
  """Final result of pipeline execution."""

  status: MessageStatus
  brd_file_path: Optional[Path] = None
  all_messages: List[AgentMessage] = field(default_factory=list)
  token_summary: Dict[str, Any] = field(default_factory=dict)
  execution_time_sec: float = 0.0
  warnings: List[str] = field(default_factory=list)
  errors: List[str] = field(default_factory=list)
  execution_id: str = ""

  def to_dict(self) -> Dict[str, Any]:
    return {
      "status": self.status.value,
      "brd_file_path": str(self.brd_file_path) if self.brd_file_path else None,
      "messages_count": len(self.all_messages),
      "token_summary": self.token_summary,
      "execution_time_sec": round(self.execution_time_sec, 2),
      "warnings": self.warnings,
      "errors": self.errors,
      "execution_id": self.execution_id,
    }
