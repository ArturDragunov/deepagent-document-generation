"""Configuration management for BRD generation system.

Supports multiple LLM providers:
- OpenAI (GPT-4, GPT-3.5-turbo, etc.)
- AWS Bedrock (Claude, Llama, etc.)
- Ollama (local models)
- Custom/other LangChain providers
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


@dataclass
class Config:
    """Configuration with support for multiple LLM providers."""

    _env_loaded: bool = False

    def __post_init__(self):
        """Load .env file once."""
        if not Config._env_loaded:
            load_dotenv()
            Config._env_loaded = True

    # ===================================================================
    # LLM Configuration (Generic, Multi-Provider Support)
    # ===================================================================

    @property
    def llm_provider(self) -> str:
        """LLM provider name: openai, bedrock, ollama, custom, etc."""
        provider = os.getenv("LLM_PROVIDER", "openai").lower()
        if not provider:
            raise ValueError("LLM_PROVIDER not set in environment or .env file")
        return provider

    @property
    def llm_model(self) -> str:
        """Model identifier for the selected provider."""
        model = os.getenv("LLM_MODEL", "gpt-4")
        if not model:
            raise ValueError("LLM_MODEL not set in environment or .env file")
        return model

    @property
    def llm_api_key(self) -> Optional[str]:
        """API key for the LLM service (varies by provider)."""
        return os.getenv("LLM_API_KEY")

    @property
    def llm_base_url(self) -> Optional[str]:
        """Optional custom base URL (for self-hosted or custom endpoints)."""
        return os.getenv("LLM_BASE_URL")

    # ===================================================================
    # Provider-Specific Configuration
    # ===================================================================

    @property
    def bedrock_region(self) -> str:
        """AWS region for Bedrock (only used if provider is 'bedrock')."""
        return os.getenv("BEDROCK_REGION", "us-east-1")

    @property
    def bedrock_profile(self) -> Optional[str]:
        """AWS profile for Bedrock credentials."""
        return os.getenv("BEDROCK_PROFILE")

    @property
    def ollama_base_url(self) -> str:
        """Ollama base URL (only used if provider is 'ollama')."""
        return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    # ===================================================================
    # File & Path Configuration
    # ===================================================================

    @property
    def corpus_dir(self) -> Path:
        """Path to corpus directory with source files."""
        path = Path(os.getenv("CORPUS_DIR", "example_data/corpus"))
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def output_dir(self) -> Path:
        """Path to output directory for generated files."""
        path = Path(os.getenv("OUTPUT_DIR", "outputs"))
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def golden_brd_path(self) -> Path:
        """Path to golden BRD reference document."""
        return Path(os.getenv("GOLDEN_BRD_PATH", "example_data/golden_brd.md"))

    @property
    def max_file_size_mb(self) -> int:
        """Maximum file size to read in MB."""
        return int(os.getenv("MAX_FILE_SIZE_MB", "50"))

    # ===================================================================
    # Agent Execution Configuration
    # ===================================================================

    @property
    def agent_timeout_sec(self) -> int:
        """Timeout per agent execution in seconds."""
        return int(os.getenv("AGENT_TIMEOUT_SEC", "60"))

    @property
    def max_retries(self) -> int:
        """Maximum retries for feedback loop in Reviewer."""
        return int(os.getenv("MAX_RETRIES", "2"))

    @property
    def use_async(self) -> bool:
        """Whether to use async execution."""
        return os.getenv("USE_ASYNC", "true").lower() == "true"

    # ===================================================================
    # Token Tracking & Cost Accounting
    # ===================================================================

    @property
    def track_tokens(self) -> bool:
        """Whether to track token usage for cost accounting."""
        return os.getenv("TRACK_TOKENS", "true").lower() == "true"

    @property
    def input_cost_per_1k_tokens(self) -> float:
        """Cost per 1k input tokens for selected model."""
        return float(os.getenv("INPUT_COST_PER_1K", "0.003"))

    @property
    def output_cost_per_1k_tokens(self) -> float:
        """Cost per 1k output tokens for selected model."""
        return float(os.getenv("OUTPUT_COST_PER_1K", "0.006"))

    def get_cost_estimate(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost estimate based on token usage."""
        return (
            (input_tokens * self.input_cost_per_1k_tokens)
            + (output_tokens * self.output_cost_per_1k_tokens)
        ) / 1000

    # ===================================================================
    # Logging Configuration
    # ===================================================================

    @property
    def log_level(self) -> str:
        """Logging level: DEBUG, INFO, WARNING, ERROR."""
        return os.getenv("LOG_LEVEL", "INFO").upper()

    @property
    def log_file(self) -> Optional[Path]:
        """Optional log file path."""
        log_file = os.getenv("LOG_FILE")
        if log_file:
            return Path(log_file)
        return None


# ===================================================================
# Global Config Singleton
# ===================================================================

_config_instance: Optional[Config] = None


def get_config() -> Config:
    """Get or create the global config instance (singleton pattern)."""
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance


def reset_config() -> None:
    """Reset config instance (useful for testing)."""
    global _config_instance
    _config_instance = None

