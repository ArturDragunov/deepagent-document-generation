"""Generic LLM factory for the BRD generation system.

Creates BaseChatModel instances from config (model string + optional provider).
Works with OpenAI, Bedrock, Ollama, etc. via langchain's init_chat_model.
"""

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

from src.config import get_config


def get_chat_model(temperature: float = 0.0) -> BaseChatModel:
  """Create a BaseChatModel from environment config.

  Uses LLM_MODEL (e.g. "openai:gpt-4") and optional LLM_MODEL_PROVIDER
  (e.g. "bedrock_converse") from config/env.

  Args:
      temperature: LLM temperature (default 0.0 for deterministic output).

  Returns:
      Configured BaseChatModel instance.
  """
  config = get_config()
  kwargs = {"model": config.llm_model, "temperature": temperature}
  if config.llm_model_provider:
    kwargs["model_provider"] = config.llm_model_provider
  return init_chat_model(**kwargs)
