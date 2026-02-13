"""Agent output file management.

Agents save their full markdown outputs to files. Downstream agents read them
via read_agent_output tool -- no truncation, full content.
"""

import os
from pathlib import Path

from src.config import get_config
from src.logger import get_logger

logger = get_logger(__name__)

_AGENT_OUTPUTS_DIR = "agent_outputs"


def _get_outputs_dir() -> Path:
  """Get the agent outputs directory (created on demand)."""
  config = get_config()
  d = config.output_dir / _AGENT_OUTPUTS_DIR
  d.mkdir(parents=True, exist_ok=True)
  return d


def save_agent_output(agent_name: str, content: str) -> str:
  """Save an agent's full markdown output to disk.

  Called by the orchestrator after each agent completes. NOT a tool for agents.

  Args:
      agent_name: Agent name (e.g. 'drool', 'model')
      content: Full markdown output from the agent.

  Returns:
      Path to the saved file.
  """
  out_dir = _get_outputs_dir()
  file_path = out_dir / f"{agent_name}_output.md"
  file_path.write_text(content, encoding="utf-8")
  logger.info("agent_output_saved", agent=agent_name, path=str(file_path), chars=len(content))
  return str(file_path)


def read_agent_output(agent_name: str) -> str:
  """Read a previous agent's full markdown output.

  Use this to get the complete output from a previous pipeline stage.
  Available agents: drool, model, outbound, transformation, inbound.

  Args:
      agent_name: Name of the agent whose output to read
                  (e.g. 'drool', 'model', 'outbound', 'transformation', 'inbound')

  Returns:
      Full markdown content from the agent, or error message if not found.
  """
  out_dir = _get_outputs_dir()
  file_path = out_dir / f"{agent_name}_output.md"

  if not file_path.exists():
    return f"ERROR: No output found for agent '{agent_name}'. Available outputs: {list_agent_outputs()}"

  content = file_path.read_text(encoding="utf-8")
  return content


def list_agent_outputs() -> str:
  """List all available agent output files.

  Returns:
      Formatted list of available agent outputs with file sizes.
  """
  out_dir = _get_outputs_dir()
  files = sorted(out_dir.glob("*_output.md"))

  if not files:
    return "No agent outputs available yet."

  lines = ["Available agent outputs:"]
  for f in files:
    name = f.stem.replace("_output", "")
    size = f.stat().st_size
    lines.append(f"  - {name} ({size:,} chars)")

  return "\n".join(lines)


def clear_agent_outputs() -> None:
  """Remove all agent output files (called at pipeline start)."""
  out_dir = _get_outputs_dir()
  for f in out_dir.glob("*_output.md"):
    f.unlink()
  logger.info("agent_outputs_cleared")
