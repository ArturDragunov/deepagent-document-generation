"""Regex tool for pattern matching on files and text.

This module provides async tool functions for deepagents integration.
Used by Drool File Filter sub-agent to match patterns in file names and content.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config import get_config


async def search_files_by_pattern(
    patterns: List[str],
    directory_filter: Optional[str] = None,
) -> str:
    """Search for files matching regex patterns in the corpus.

    Useful for the Drool File Filter to identify relevant files based on keywords.

    Args:
        patterns: List of regex patterns to match (e.g., ['LC\\d+', 'spec', 'requirements'])
        directory_filter: Optional directory prefix to filter search (e.g., 'drools', 'models')

    Returns:
        Formatted list of matching files with match details.
    """
    config = get_config()
    corpus_dir = config.corpus_dir

    if not corpus_dir.exists():
        return f"ERROR: Corpus directory not found: {corpus_dir}"

    try:
        # Get all file paths
        if directory_filter:
            search_dir = corpus_dir / directory_filter
            if not search_dir.exists():
                return f"ERROR: Directory not found: {directory_filter}"
            files = list(search_dir.rglob("*"))
        else:
            files = list(corpus_dir.rglob("*"))

        files = [f for f in files if f.is_file()]
        if not files:
            return f"No files found in {directory_filter or 'corpus'}"

        # Compile patterns
        compiled_patterns = []
        for pattern in patterns:
            try:
                compiled_patterns.append((pattern, re.compile(pattern, re.IGNORECASE)))
            except re.error as e:
                return f"ERROR: Invalid regex pattern '{pattern}': {e}"

        # Match files
        matches = {}
        for file_path in files:
            file_name = file_path.name
            relative_path = str(file_path.relative_to(corpus_dir))

            matched_patterns = []
            for pattern_str, compiled_pattern in compiled_patterns:
                if compiled_pattern.search(file_name):
                    matched_patterns.append(pattern_str)

            if matched_patterns:
                matches[relative_path] = matched_patterns

        # Format output
        if not matches:
            return f"No files matched patterns: {', '.join(patterns)}"

        output = f"Found {len(matches)} matching files:\n"
        for file_path in sorted(matches.keys()):
            patterns_matched = ", ".join(matches[file_path])
            output += f"  - {file_path} (matched: {patterns_matched})\n"

        return output

    except Exception as e:
        return f"ERROR: Pattern search failed: {str(e)}"


async def match_patterns_in_text(
    text: str,
    patterns: List[str],
) -> str:
    """Match multiple regex patterns against text content.

    Args:
        text: Text content to search in
        patterns: List of regex patterns to match

    Returns:
        Formatted list of matches with context.
    """
    try:
        # Compile patterns
        compiled_patterns = []
        for pattern in patterns:
            try:
                compiled_patterns.append((pattern, re.compile(pattern, re.IGNORECASE)))
            except re.error as e:
                return f"ERROR: Invalid regex pattern '{pattern}': {e}"

        # Find matches
        all_matches = {}
        for pattern_str, compiled_pattern in compiled_patterns:
            matches = list(compiled_pattern.finditer(text))
            if matches:
                all_matches[pattern_str] = [m.group(0) for m in matches]

        # Format output
        if not all_matches:
            return f"No matches found for patterns: {', '.join(patterns)}"

        output = f"Matched {sum(len(v) for v in all_matches.values())} occurrences:\n"
        for pattern, matches in all_matches.items():
            output += f"  Pattern '{pattern}': {len(matches)} matches\n"
            # Show first 3 matches
            for match in matches[:3]:
                output += f"    - {match}\n"
            if len(matches) > 3:
                output += f"    ... and {len(matches) - 3} more\n"

        return output

    except Exception as e:
        return f"ERROR: Pattern matching failed: {str(e)}"


async def extract_keywords(text: str) -> str:
    """Extract potential keywords from text for use in pattern generation.

    Useful for Drool File Filter to identify relevant keywords from user query.

    Args:
        text: Text to extract keywords from

    Returns:
        Formatted list of extracted keywords.
    """
    try:
        # Extract common patterns
        codes = re.findall(r'\b[A-Z]{2}\d{4}\b', text)  # e.g., LC0070
        words = re.findall(r'\b[a-z]{4,}\b', text.lower())  # Words > 4 chars
        camelcase = re.findall(r'\b[a-z]+[A-Z][a-zA-Z]*\b', text)  # CamelCase

        extracted = {
            "codes": list(set(codes)),
            "words": list(set(words))[:10],  # Top 10
            "camelcase": list(set(camelcase))[:5],
        }

        output = "Extracted keywords:\n"
        output += f"  Codes: {', '.join(extracted['codes']) or 'None'}\n"
        output += f"  Words: {', '.join(extracted['words']) or 'None'}\n"
        output += f"  CamelCase: {', '.join(extracted['camelcase']) or 'None'}\n"

        return output

    except Exception as e:
        return f"ERROR: Keyword extraction failed: {str(e)}"
