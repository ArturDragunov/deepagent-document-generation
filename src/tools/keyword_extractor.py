"""Keyword extraction tool for deepagents.

Extracts potential keywords and patterns from user queries for use by the
Drool File Filter sub-agent. Synchronous (deepagents requirement).
"""

import re
from typing import List


def extract_keywords(text: str) -> str:
  """Extract potential keywords and code patterns from text for file filtering.

  Identifies business codes (e.g. LC0070), technical terms, camelCase identifiers,
  and significant words. Used by the Drool File Filter to generate search patterns.

  Args:
      text: Text to extract keywords from (typically the user query).

  Returns:
      Formatted string listing extracted keywords grouped by type.
  """
  try:
    codes = list(set(re.findall(r"\b[A-Z]{2}\d{3,5}\b", text)))
    acronyms = list(set(re.findall(r"\b[A-Z]{2,6}\b", text)))
    camelcase = list(set(re.findall(r"\b[a-z]+[A-Z][a-zA-Z]*\b", text)))

    # Significant words (4+ chars, lowercase, deduplicated)
    stopwords = {
      "this", "that", "with", "from", "have", "will", "been",
      "they", "their", "about", "would", "could", "should",
      "which", "there", "these", "those", "what", "when",
      "where", "some", "each", "based", "also", "like",
    }
    words = list(set(
      w for w in re.findall(r"\b[a-z]{4,}\b", text.lower())
      if w not in stopwords
    ))[:15]

    output = "Extracted keywords:\n"
    output += f"  Codes: {', '.join(codes) or 'None'}\n"
    output += f"  Acronyms: {', '.join(acronyms) or 'None'}\n"
    output += f"  CamelCase: {', '.join(camelcase) or 'None'}\n"
    output += f"  Words: {', '.join(words) or 'None'}\n"

    # Suggest regex patterns for file search
    patterns = _generate_search_patterns(codes, words, acronyms)
    if patterns:
      output += f"\nSuggested search patterns:\n"
      for p in patterns:
        output += f"  - {p}\n"

    return output
  except Exception as e:
    return f"ERROR: Keyword extraction failed: {e}"


def _generate_search_patterns(
  codes: List[str],
  words: List[str],
  acronyms: List[str],
) -> List[str]:
  """Generate regex patterns for file searching."""
  patterns = []
  for code in codes:
    patterns.append(code)
    patterns.append(code.lower())
  for word in words[:5]:
    patterns.append(word)
  for acr in acronyms[:3]:
    if len(acr) >= 3:
      patterns.append(acr)
  return patterns
