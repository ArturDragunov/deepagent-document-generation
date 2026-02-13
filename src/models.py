"""Data models and type definitions for BRD generation system."""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class AgentType(str, Enum):
    """Types of agents in the system."""

    MANAGER = "manager"
    SUB_AGENT = "sub_agent"


class SubAgentType(str, Enum):
    """Types of sub-agents."""

    ANALYSIS = "analysis"
    SYNTHESIS = "synthesis"
    WRITER = "writer"
    REVIEW = "review"
    FILE_FILTER = "file_filter"


class MessageStatus(str, Enum):
    """Status of agent message execution."""

    SUCCESS = "success"
    TIMEOUT = "timeout"
    ERROR = "error"
    PARTIAL = "partial"
    FALLBACK = "fallback"


@dataclass
class TokenAccount:
    """Tracks token usage for a single agent or execution."""

    agent_id: str
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_tokens: int = 0
    cost_estimate: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
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
    sub_type: Optional[SubAgentType] = None
    markdown_content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    parent_message_id: Optional[str] = None
    execution_timestamp: datetime = field(default_factory=datetime.now)
    duration_ms: float = 0.0
    token_account: Optional[TokenAccount] = None
    status: MessageStatus = MessageStatus.SUCCESS

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type.value,
            "sub_type": self.sub_type.value if self.sub_type else None,
            "markdown_content": self.markdown_content[:500],  # Truncate for logging
            "metadata": self.metadata,
            "parent_message_id": self.parent_message_id,
            "execution_timestamp": self.execution_timestamp.isoformat(),
            "duration_ms": round(self.duration_ms, 2),
            "token_account": self.token_account.to_dict()
            if self.token_account
            else None,
            "status": self.status.value,
        }


@dataclass
class TokenTracker:
    """Tracks token usage across entire execution."""

    accounts: List[TokenAccount] = field(default_factory=list)

    def record_estimate(
        self, agent_id: str, input_tokens: int, output_tokens: int
    ) -> None:
        """Record estimated token usage."""
        account = TokenAccount(
            agent_id=agent_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_tokens=input_tokens + output_tokens,
        )
        self.accounts.append(account)

    def record_actual(
        self, agent_id: str, api_response: Dict[str, Any]
    ) -> None:
        """Record actual tokens from API response."""
        usage = api_response.get("usage", {})
        # Find matching account by agent_id (most recent)
        matching_accounts = [
            a for a in self.accounts if a.agent_id == agent_id
        ]
        if matching_accounts:
            account = matching_accounts[-1]
            account.input_tokens = usage.get("prompt_tokens", 0)
            account.output_tokens = usage.get("completion_tokens", 0)

    def update_cost_estimate(
        self, agent_id: str, input_cost_rate: float, output_cost_rate: float
    ) -> None:
        """Update cost estimate for an agent."""
        matching_accounts = [
            a for a in self.accounts if a.agent_id == agent_id
        ]
        if matching_accounts:
            account = matching_accounts[-1]
            account.cost_estimate = (
                (account.input_tokens * input_cost_rate)
                + (account.output_tokens * output_cost_rate)
            ) / 1000

    def get_summary(self) -> Dict[str, Any]:
        """Get aggregated summary of token usage."""
        return {
            "total_input_tokens": sum(a.input_tokens for a in self.accounts),
            "total_output_tokens": sum(a.output_tokens for a in self.accounts),
            "total_estimated_tokens": sum(
                a.estimated_tokens for a in self.accounts
            ),
            "total_cost_estimate": round(
                sum(a.cost_estimate for a in self.accounts), 6
            ),
            "agent_count": len(set(a.agent_id for a in self.accounts)),
            "accounts": [a.to_dict() for a in self.accounts],
        }


@dataclass
class ExecutionContext:
    """Shared execution context for the entire pipeline."""

    user_query: str
    corpus_files: List[str]
    all_messages: List[AgentMessage] = field(default_factory=list)
    token_tracker: TokenTracker = field(default_factory=TokenTracker)
    output_dir: Path = field(default_factory=lambda: Path("outputs"))
    max_timeout_sec: int = 60
    retry_count: int = 2
    start_time: datetime = field(default_factory=datetime.now)
    execution_id: str = field(default_factory=lambda: datetime.now().isoformat())

    def add_message(self, message: AgentMessage) -> None:
        """Add a message to the execution context."""
        self.all_messages.append(message)

    def get_messages_by_agent(self, agent_id: str) -> List[AgentMessage]:
        """Get all messages from a specific agent."""
        return [msg for msg in self.all_messages if msg.agent_id == agent_id]

    def get_messages_by_type(
        self, agent_type: AgentType
    ) -> List[AgentMessage]:
        """Get all messages of a specific agent type."""
        return [msg for msg in self.all_messages if msg.agent_type == agent_type]

    def get_latest_message(self) -> Optional[AgentMessage]:
        """Get the most recent message."""
        return self.all_messages[-1] if self.all_messages else None

    def get_elapsed_time_sec(self) -> float:
        """Get elapsed execution time in seconds."""
        return (datetime.now() - self.start_time).total_seconds()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/serialization."""
        return {
            "user_query": self.user_query[:200],  # Truncate for logging
            "corpus_files_count": len(self.corpus_files),
            "messages_count": len(self.all_messages),
            "elapsed_time_sec": round(self.get_elapsed_time_sec(), 2),
            "execution_id": self.execution_id,
            "token_summary": self.token_tracker.get_summary(),
        }


@dataclass
class ReprocessRequest:
    """Request from Reviewer for a manager to reprocess a section."""

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
        """Convert to dictionary."""
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
