"""Token estimation and cost calculation tool for deepagents.

All functions are synchronous (deepagents requirement).
"""

import tiktoken

from src.config import get_config


def estimate_tokens(text: str, model: str = "gpt-4") -> str:
  """Estimate the number of tokens in the given text.

  Args:
      text: Text to estimate tokens for.
      model: Model name for tokenizer selection (default: gpt-4).

  Returns:
      Formatted string with token count and cost estimate.
  """
  try:
    try:
      encoding = tiktoken.encoding_for_model(model)
    except KeyError:
      encoding = tiktoken.get_encoding("cl100k_base")

    token_count = len(encoding.encode(text))

    config = get_config()
    cost = (token_count * config.input_cost_per_1k_tokens) / 1000

    return (
      f"Token estimate ({model}):\n"
      f"  Characters: {len(text)}\n"
      f"  Tokens: {token_count}\n"
      f"  Est. input cost: ${cost:.6f}\n"
    )
  except Exception as e:
    return f"ERROR: Token estimation failed: {e}"


def calculate_cost(input_tokens: int, output_tokens: int) -> str:
  """Calculate total cost for given token counts.

  Args:
      input_tokens: Number of input (prompt) tokens.
      output_tokens: Number of output (completion) tokens.

  Returns:
      Formatted cost breakdown string.
  """
  try:
    config = get_config()
    input_cost = (input_tokens * config.input_cost_per_1k_tokens) / 1000
    output_cost = (output_tokens * config.output_cost_per_1k_tokens) / 1000
    total = input_cost + output_cost

    return (
      f"Cost breakdown:\n"
      f"  Input:  {input_tokens} tokens -> ${input_cost:.6f}\n"
      f"  Output: {output_tokens} tokens -> ${output_cost:.6f}\n"
      f"  Total:  {input_tokens + output_tokens} tokens -> ${total:.6f}\n"
    )
  except Exception as e:
    return f"ERROR: Cost calculation failed: {e}"
