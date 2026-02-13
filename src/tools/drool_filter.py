"""LLM-based drool file filter.

Replaces the regex/keyword-based approach. For each drool file, makes a simple
LLM call comparing file content to the user query, returning a structured
include/exclude verdict via Pydantic.
"""

import asyncio
from typing import Dict, List

from pydantic import BaseModel, Field

from src.llm import get_chat_model
from src.logger import get_logger
from src.tools.corpus_reader import read_corpus_file

logger = get_logger(__name__)


class FileRelevance(BaseModel):
  """Structured output for file relevance classification."""

  include: bool = Field(description="Whether this file is relevant to the user query")
  reason: str = Field(description="Brief explanation for the decision")


async def filter_drool_files(
  user_query: str,
  file_paths: List[str],
) -> Dict[str, List[str]]:
  """Filter drool/corpus files by relevance using LLM calls.

  For each file, reads its content and asks the LLM whether it's relevant
  to the user query. Returns included/excluded file lists.

  Args:
      user_query: The user's BRD generation query.
      file_paths: List of file paths (relative to corpus dir) to evaluate.

  Returns:
      Dict with "included" and "excluded" file path lists.
  """
  if not file_paths:
    return {"included": [], "excluded": []}

  llm = get_chat_model(temperature=0.0).with_structured_output(FileRelevance)

  included = []
  excluded = []

  for path in file_paths:
    try:
      content = read_corpus_file(path)

      if content.startswith("ERROR:"):
        logger.warning("drool_filter_skip", file=path, reason=content)
        excluded.append(path)
        continue

      prompt = (
        f"You are a file relevance filter. Determine if this file contains "
        f"information relevant to the following user query.\n\n"
        f"USER QUERY: {user_query}\n\n"
        f"FILE: {path}\n"
        f"CONTENT:\n{content}\n\n"
        f"Be CONSERVATIVE -- include files that might be even tangentially related. "
        f"Better to include too many than miss something important."
      )

      result = await llm.ainvoke(prompt)

      if result.include:
        included.append(path)
        logger.info("drool_filter_include", file=path, reason=result.reason)
      else:
        excluded.append(path)
        logger.info("drool_filter_exclude", file=path, reason=result.reason)

    except Exception as e:
      # On error, be conservative and include the file
      logger.warning("drool_filter_error", file=path, error=str(e))
      included.append(path)

  logger.info(
    "drool_filter_complete",
    total=len(file_paths),
    included=len(included),
    excluded=len(excluded),
  )

  return {"included": included, "excluded": excluded}
