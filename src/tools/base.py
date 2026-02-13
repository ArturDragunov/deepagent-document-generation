"""Base Tool class for all agent tools."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ToolParameter:
    """Definition of a tool parameter."""

    name: str
    description: str
    type: str
    required: bool = True
    default: Optional[Any] = None


class BaseTool(ABC):
    """Abstract base class for all tools used by agents."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name identifier for the tool."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what the tool does."""
        pass

    @property
    def parameters(self) -> List[ToolParameter]:
        """List of tool parameters. Override in subclass if needed."""
        return []

    def to_dict(self) -> Dict[str, Any]:
        """Convert tool definition to dictionary for deepagents."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": [
                {
                    "name": p.name,
                    "description": p.description,
                    "type": p.type,
                    "required": p.required,
                    "default": p.default,
                }
                for p in self.parameters
            ],
        }

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """Execute the tool with given arguments."""
        pass

    async def __call__(self, **kwargs) -> Any:
        """Allow tool to be called directly."""
        return await self.execute(**kwargs)
