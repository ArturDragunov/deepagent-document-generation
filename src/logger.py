"""Custom structured logger for the BRD generation system.

Uses structlog for JSON-structured logging with console + file output.
Based on: https://github.com/ArturDragunov/bookwise-recommendation
"""

import os
import logging
from datetime import datetime

import structlog


class CustomLogger:
  """Structured logger with file + console output."""

  _instance = None
  _initialized = False

  def __new__(cls, log_dir: str = "logs"):
    if cls._instance is None:
      cls._instance = super().__new__(cls)
    return cls._instance

  def __init__(self, log_dir: str = "logs"):
    if CustomLogger._initialized:
      return
    CustomLogger._initialized = True

    self.logs_dir = os.path.join(os.getcwd(), log_dir)
    os.makedirs(self.logs_dir, exist_ok=True)

    log_file = f"{datetime.now().strftime('%m_%d_%Y_%H_%M_%S')}.log"
    self.log_file_path = os.path.join(self.logs_dir, log_file)

    self._configure()

  def _configure(self):
    """Configure structlog + stdlib logging once."""
    file_handler = logging.FileHandler(self.log_file_path)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter("%(message)s"))

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter("%(message)s"))

    logging.basicConfig(
      level=logging.INFO,
      format="%(message)s",
      handlers=[console_handler, file_handler],
    )

    # Suppress noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    structlog.configure(
      processors=[
        structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"),
        structlog.processors.add_log_level,
        structlog.processors.EventRenamer(to="event"),
        structlog.processors.JSONRenderer(),
      ],
      logger_factory=structlog.stdlib.LoggerFactory(),
      cache_logger_on_first_use=True,
    )

  def get_logger(self, name: str = __file__):
    """Get a structlog logger instance for a module."""
    logger_name = os.path.basename(name)
    return structlog.get_logger(logger_name)


def get_logger(name: str = __file__):
  """Convenience function to get a logger instance.

  Usage:
      from src.logger import get_logger
      logger = get_logger(__name__)
      logger.info("something happened", key="value")
  """
  return CustomLogger().get_logger(name)
