"""Token estimator tool with dual tracking (estimated + actual).

This module provides async tool functions for deepagents integration.
Estimates token usage and calculates costs based on model pricing.
"""

import tiktoken
from typing import Any, Dict, Optional

from src.config import get_config


async def estimate_tokens_in_text(text: str, model: str = "gpt-4") -> str:
    """Estimate the number of tokens in the given text.

    Useful for cost accounting and monitoring token usage per agent.

    Args:
        text: Text to estimate tokens for
        model: Model name for token estimation (default: gpt-4)

    Returns:
        Formatted string with token count and cost estimate.
    """
    try:
        # Get the right encoding for the model
        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            encoding = tiktoken.get_encoding("cl100k_base")

        # Estimate tokens
        tokens = encoding.encode(text)
        token_count = len(tokens)

        # Calculate cost
        config = get_config()
        cost_per_1k = config.gpt4_input_cost_per_1k_tokens / 1000
        estimated_cost = (token_count * cost_per_1k)

        output = f"Token Estimation for {model}:\n"
        output += f"  Text length: {len(text)} characters\n"
        output += f"  Estimated tokens: {token_count}\n"
        output += f"  Estimated cost (input): ${estimated_cost:.6f}\n"

        return output

    except Exception as e:
        return f"ERROR: Token estimation failed: {str(e)}"


async def calculate_cost(
    input_tokens: int,
    output_tokens: int,
    model: str = "gpt-4",
) -> str:
    """Calculate the total cost for given token counts.

    Args:
        input_tokens: Number of input (prompt) tokens
        output_tokens: Number of output (completion) tokens
        model: Model name for cost calculation (default: gpt-4)

    Returns:
        Formatted string with cost breakdown.
    """
    try:
        config = get_config()

        input_cost = (input_tokens * config.gpt4_input_cost_per_1k_tokens) / 1000
        output_cost = (output_tokens * config.gpt4_output_cost_per_1k_tokens) / 1000
        total_cost = input_cost + output_cost

        output = f"Cost Calculation for {model}:\n"
        output += f"  Input tokens: {input_tokens}\n"
        output += f"  Output tokens: {output_tokens}\n"
        output += f"  Total tokens: {input_tokens + output_tokens}\n"
        output += f"  Input cost: ${input_cost:.6f}\n"
        output += f"  Output cost: ${output_cost:.6f}\n"
        output += f"  TOTAL COST: ${total_cost:.6f}\n"

        return output

    except Exception as e:
        return f"ERROR: Cost calculation failed: {str(e)}"
