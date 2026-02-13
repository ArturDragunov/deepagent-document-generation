"""LLM client factory for multiple providers.

Supports OpenAI, AWS Bedrock, Ollama, and other LangChain providers.
Returns LangChain BaseChatModel instances for use with deepagents.
"""

from typing import Optional

from langchain.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_aws import ChatBedrock
from langchain_ollama import ChatOllama

from src.config import get_config


def get_llm_client(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
) -> BaseChatModel:
    """
    Get a LangChain ChatModel instance for the specified LLM provider.

    Args:
        provider: LLM provider name (openai, bedrock, ollama, etc.)
        model: Model identifier for the provider
        api_key: API key (varies by provider)
        base_url: Custom base URL (for Ollama or custom endpoints)
        temperature: Sampling temperature (0-2)
        max_tokens: Maximum tokens in response

    Returns:
        LangChain BaseChatModel instance configured for the provider
    """
    config = get_config()

    provider = provider or config.llm_provider
    model = model or config.llm_model
    api_key = api_key or config.llm_api_key
    base_url = base_url or config.llm_base_url

    provider = provider.lower()

    if provider == "openai":
        return ChatOpenAI(
            api_key=api_key,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            base_url=base_url if base_url else None,
        )

    elif provider == "bedrock":
        return ChatBedrock(
            model_id=model,
            region_name=config.bedrock_region,
            profile_name=config.bedrock_profile,
            model_kwargs={
                "temperature": temperature,
                **({"max_tokens": max_tokens} if max_tokens else {})
            },
        )

    elif provider == "ollama":
        return ChatOllama(
            model=model,
            base_url=base_url or config.ollama_base_url,
            temperature=temperature,
        )

    else:
        raise ValueError(
            f"Unsupported LLM provider: {provider}. "
            f"Supported providers: openai, bedrock, ollama"
        )
