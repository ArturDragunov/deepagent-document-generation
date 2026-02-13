"""Configuration management for BRD generation system.

All settings are loaded from environment variables / .env file.
LLM model is specified as a deepagents-compatible string (e.g. "openai:gpt-4").
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


@dataclass
class Config:
  """Application configuration loaded from environment."""

  _env_loaded: bool = False

  def __post_init__(self):
    if not Config._env_loaded:
      load_dotenv()  # .env
      load_dotenv(".env.local")  # local overrides (e.g. API keys, LLM_MODEL)
      Config._env_loaded = True

  # =================================================================
  # LLM Configuration
  # =================================================================

  @property
  def llm_model(self) -> str:
    """Model string for deepagents (e.g. 'openai:gpt-4', 'anthropic.claude-3-5-sonnet-20240620-v1:0')."""
    return os.getenv("LLM_MODEL", "openai:gpt-4")

  @property
  def llm_model_provider(self) -> Optional[str]:
    """Optional model provider override (e.g. 'bedrock_converse'). Only needed for Bedrock."""
    return os.getenv("LLM_MODEL_PROVIDER")

  # =================================================================
  # File & Path Configuration
  # =================================================================

  @property
  def corpus_dir(self) -> Path:
    path = Path(os.getenv("CORPUS_DIR", "example_data/corpus"))
    path.mkdir(parents=True, exist_ok=True)
    return path

  @property
  def output_dir(self) -> Path:
    path = Path(os.getenv("OUTPUT_DIR", "outputs"))
    path.mkdir(parents=True, exist_ok=True)
    return path

  @property
  def file_group_delimiter(self) -> str:
    """Delimiter for grouping files by workbook (e.g. '_sheet' -> workbook_A_sheet1.jsonl + workbook_A_sheet2.jsonl)."""
    return os.getenv("FILE_GROUP_DELIMITER", "_sheet")

  @property
  def max_files_per_group(self) -> int:
    """Max files per run; groups larger than this are split (e.g. 20 sheets in one workbook -> 3 runs of 8)."""
    return int(os.getenv("MAX_FILES_PER_GROUP", "8"))

  @property
  def consolidate_sections(self) -> bool:
    """If True, after batch runs run one short consolidation step with golden BRD to produce one coherent doc."""
    return os.getenv("CONSOLIDATE_SECTIONS", "true").lower() == "true"

  @property
  def golden_brd_path(self) -> Path:
    return Path(os.getenv("GOLDEN_BRD_PATH", "example_data/golden_brd.md"))

  @property
  def max_file_size_mb(self) -> int:
    return int(os.getenv("MAX_FILE_SIZE_MB", "50"))

  # =================================================================
  # Agent Execution
  # =================================================================

  @property
  def agent_timeout_sec(self) -> int:
    return int(os.getenv("AGENT_TIMEOUT_SEC", "300"))

  @property
  def reviewer_timeout_sec(self) -> int:
    return int(os.getenv("REVIEWER_TIMEOUT_SEC", "600"))

  @property
  def max_retries(self) -> int:
    return int(os.getenv("MAX_RETRIES", "2"))

  # =================================================================
  # Token Tracking & Cost
  # =================================================================

  @property
  def track_tokens(self) -> bool:
    return os.getenv("TRACK_TOKENS", "true").lower() == "true"

  @property
  def input_cost_per_1k_tokens(self) -> float:
    return float(os.getenv("INPUT_COST_PER_1K", "0.003"))

  @property
  def output_cost_per_1k_tokens(self) -> float:
    return float(os.getenv("OUTPUT_COST_PER_1K", "0.006"))

  def get_cost_estimate(self, input_tokens: int, output_tokens: int) -> float:
    return (
      (input_tokens * self.input_cost_per_1k_tokens)
      + (output_tokens * self.output_cost_per_1k_tokens)
    ) / 1000

  # =================================================================
  # Logging
  # =================================================================

  @property
  def log_level(self) -> str:
    return os.getenv("LOG_LEVEL", "INFO").upper()


# =================================================================
# Global Singleton
# =================================================================

_config_instance: Optional[Config] = None


def get_config() -> Config:
  global _config_instance
  if _config_instance is None:
    _config_instance = Config()
  return _config_instance


def reset_config() -> None:
  global _config_instance
  _config_instance = None
