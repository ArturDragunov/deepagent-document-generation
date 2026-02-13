"""File reader tool for accessing corpus files.

This module provides async tool functions for deepagents integration.
No class wrappers - just pure async functions that deepagents can call directly.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import polars as pl

from src.config import get_config


# ============================================================================
# Async Tool Functions for DeepAgents
# ============================================================================
# These are called directly by deepagents agents
# Names and docstrings are critical - they become the tool schema


async def read_file(file_path: str, max_bytes: Optional[int] = None) -> str:
    """Read a file from the corpus directory and return its content as formatted text.

    Supports JSONL, JSON, CSV, markdown, text, and Excel formats.
    For structured formats (JSON/JSONL/CSV), returns formatted text representation.

    Args:
        file_path: Path to file relative to corpus directory (e.g., 'models/model.json' or 'drools/spec.md')
        max_bytes: Maximum bytes to read. If not specified, uses config max_file_size_mb setting.

    Returns:
        File content as formatted string, or error message if file cannot be read.
    """
    config = get_config()
    corpus_dir = config.corpus_dir
    full_path = corpus_dir / file_path

    if not full_path.exists():
        return f"ERROR: File not found: {file_path}"

    file_size_bytes = full_path.stat().st_size
    max_bytes = max_bytes or (config.max_file_size_mb * 1024 * 1024)

    if file_size_bytes > max_bytes:
        return f"ERROR: File too large ({file_size_bytes / 1024 / 1024:.2f}MB, max {config.max_file_size_mb}MB)"

    try:
        suffix = full_path.suffix.lower()

        if suffix == ".jsonl":
            return _read_jsonl_as_text(full_path)
        elif suffix == ".json":
            return _read_json_as_text(full_path)
        elif suffix == ".csv":
            return _read_csv_as_text(full_path)
        elif suffix == ".xlsx":
            return _read_excel_as_text(full_path)
        else:  # .md, .txt, .text, etc.
            return _read_text_as_text(full_path)

    except Exception as e:
        return f"ERROR: Failed to read file: {str(e)}"


async def list_corpus_files(pattern: str = "*") -> str:
    """List all files in the corpus directory matching a pattern.

    Useful for exploring available files before reading them.

    Args:
        pattern: Glob pattern to match file names (e.g., '*.jsonl', 'drools/*', etc.)

    Returns:
        Formatted list of files found, or message if none found.
    """
    config = get_config()
    corpus_dir = config.corpus_dir

    try:
        files = sorted([
            str(f.relative_to(corpus_dir))
            for f in corpus_dir.glob(pattern)
            if f.is_file()
        ])

        if not files:
            return f"No files found matching pattern '{pattern}' in corpus"

        return f"Found {len(files)} files:\n" + "\n".join(f"  - {f}" for f in files)

    except Exception as e:
        return f"ERROR: Failed to list files: {str(e)}"


# ============================================================================
# Helper Functions (Internal Use)
# ============================================================================


def _read_jsonl_as_text(file_path: Path, max_rows: int = 20) -> str:
    """Read JSONL file and format as text."""
    try:
        df = pl.read_ndjson(str(file_path))
        rows = len(df)
        cols = df.columns

        # Truncate if too many rows
        if rows > max_rows:
            df = df.head(max_rows)

        content = f"JSONL File: {file_path.name}\n"
        content += f"Total rows: {rows}, Columns: {', '.join(cols)}\n"
        content += f"Data (first {min(rows, max_rows)} rows):\n"
        content += df.to_csv()

        return content
    except Exception as e:
        return f"ERROR reading JSONL: {str(e)}"


def _read_json_as_text(file_path: Path) -> str:
    """Read JSON file and format as text."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        content = f"JSON File: {file_path.name}\n"
        content += json.dumps(data, indent=2)[:5000]  # Truncate long JSON

        return content
    except Exception as e:
        return f"ERROR reading JSON: {str(e)}"


def _read_csv_as_text(file_path: Path, max_rows: int = 20) -> str:
    """Read CSV file and format as text."""
    try:
        df = pl.read_csv(str(file_path))
        rows = len(df)

        if rows > max_rows:
            df = df.head(max_rows)

        content = f"CSV File: {file_path.name}\n"
        content += f"Total rows: {rows}, Columns: {', '.join(df.columns)}\n"
        content += df.to_csv()

        return content
    except Exception as e:
        return f"ERROR reading CSV: {str(e)}"


def _read_excel_as_text(file_path: Path, max_rows: int = 20) -> str:
    """Read Excel file and format as text."""
    try:
        df = pl.read_excel(str(file_path))
        rows = len(df)

        if rows > max_rows:
            df = df.head(max_rows)

        content = f"Excel File: {file_path.name}\n"
        content += f"Total rows: {rows}, Columns: {', '.join(df.columns)}\n"
        content += df.to_csv()

        return content
    except Exception as e:
        return f"ERROR reading Excel: {str(e)}"


def _read_text_as_text(file_path: Path, max_chars: int = 10000) -> str:
    """Read text/markdown file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        if len(content) > max_chars:
            content = content[:max_chars] + "\n... (truncated)"

        return content
    except Exception as e:
        return f"ERROR reading text file: {str(e)}"
