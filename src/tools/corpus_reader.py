"""Format-aware corpus file reader tool for deepagents.

Supports: JSONL, JSON, CSV, Excel, PDF, Word (.docx), Drools (.drl),
Markdown, and plain text. All functions are synchronous (deepagents requirement).

NO artificial truncation -- returns full file content. The only hard limit
is MAX_FILE_SIZE_MB from config (default 50MB) which prevents accidentally
loading huge binary files.
"""

import json
from pathlib import Path
from typing import Optional

import polars as pl

from src.config import get_config


def read_corpus_file(file_path: str, max_lines: Optional[int] = None) -> str:
  """Read a file from the corpus directory and return its FULL content.

  Supports JSONL, JSON, CSV, Excel (.xlsx), PDF, Word (.docx), Drools (.drl),
  Markdown (.md), and plain text formats. For structured formats, returns a
  text representation suitable for LLM consumption.

  Args:
      file_path: Path to file relative to corpus directory (e.g. 'drools/LC0070.drl')
      max_lines: Optional max lines/rows for tabular data. None = no limit (all rows).

  Returns:
      File content as formatted string, or error message if file cannot be read.
  """
  config = get_config()
  corpus_dir = config.corpus_dir
  full_path = corpus_dir / file_path

  if not full_path.exists():
    return f"ERROR: File not found: {file_path}"

  file_size_bytes = full_path.stat().st_size
  max_bytes = config.max_file_size_mb * 1024 * 1024

  if file_size_bytes > max_bytes:
    return (
      f"ERROR: File too large ({file_size_bytes / 1024 / 1024:.1f}MB, "
      f"max {config.max_file_size_mb}MB)"
    )

  suffix = full_path.suffix.lower()

  try:
    if suffix == ".jsonl":
      return _read_jsonl(full_path, max_lines)
    elif suffix == ".json":
      return _read_json(full_path)
    elif suffix == ".csv":
      return _read_csv(full_path, max_lines)
    elif suffix == ".xlsx":
      return _read_excel(full_path, max_lines)
    elif suffix == ".pdf":
      return _read_pdf(full_path)
    elif suffix == ".docx":
      return _read_word(full_path)
    elif suffix == ".drl":
      return _read_text(full_path)
    else:
      return _read_text(full_path)
  except Exception as e:
    return f"ERROR: Failed to read {file_path}: {e}"


# ---------------------------------------------------------------------------
# Internal format readers -- no artificial truncation
# ---------------------------------------------------------------------------

def _read_jsonl(path: Path, max_rows: Optional[int] = None) -> str:
  try:
    df = pl.read_ndjson(str(path))
  except Exception:
    # Fallback: read line-by-line as raw JSON objects
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    rows = len(lines)
    if max_rows and rows > max_rows:
      preview = lines[:max_rows]
      content = f"JSONL File: {path.name} ({rows} lines, showing {max_rows})\n"
      for line in preview:
        content += line + "\n"
      content += f"... ({rows - max_rows} more lines)\n"
    else:
      content = f"JSONL File: {path.name} ({rows} lines)\n"
      for line in lines:
        content += line + "\n"
    return content

  rows = len(df)
  cols = df.columns
  if max_rows and rows > max_rows:
    content = f"JSONL File: {path.name}\n"
    content += f"Rows: {rows} (showing {max_rows}), Columns: {', '.join(cols)}\n"
    content += df.head(max_rows).write_csv()
    content += f"\n... ({rows - max_rows} more rows)\n"
  else:
    content = f"JSONL File: {path.name}\n"
    content += f"Rows: {rows}, Columns: {', '.join(cols)}\n"
    content += df.write_csv()
  return content


def _read_json(path: Path) -> str:
  with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)
  content = f"JSON File: {path.name}\n"
  content += json.dumps(data, indent=2)
  return content


def _read_csv(path: Path, max_rows: Optional[int] = None) -> str:
  df = pl.read_csv(str(path))
  rows = len(df)
  if max_rows and rows > max_rows:
    content = f"CSV File: {path.name}\n"
    content += f"Rows: {rows} (showing {max_rows}), Columns: {', '.join(df.columns)}\n"
    content += df.head(max_rows).write_csv()
    content += f"\n... ({rows - max_rows} more rows)\n"
  else:
    content = f"CSV File: {path.name}\n"
    content += f"Rows: {rows}, Columns: {', '.join(df.columns)}\n"
    content += df.write_csv()
  return content


def _read_excel(path: Path, max_rows: Optional[int] = None) -> str:
  df = pl.read_excel(str(path))
  rows = len(df)
  if max_rows and rows > max_rows:
    content = f"Excel File: {path.name}\n"
    content += f"Rows: {rows} (showing {max_rows}), Columns: {', '.join(df.columns)}\n"
    content += df.head(max_rows).write_csv()
    content += f"\n... ({rows - max_rows} more rows)\n"
  else:
    content = f"Excel File: {path.name}\n"
    content += f"Rows: {rows}, Columns: {', '.join(df.columns)}\n"
    content += df.write_csv()
  return content


def _read_pdf(path: Path) -> str:
  try:
    import pymupdf  # PyMuPDF
  except ImportError:
    return "ERROR: pymupdf not installed. Run: pip install pymupdf"

  doc = pymupdf.open(str(path))
  content = f"PDF File: {path.name} ({len(doc)} pages)\n\n"
  for page_num, page in enumerate(doc, 1):
    text = page.get_text()
    content += f"--- Page {page_num} ---\n{text}\n"
  doc.close()
  return content


def _read_word(path: Path) -> str:
  try:
    from docx import Document
  except ImportError:
    return "ERROR: python-docx not installed. Run: pip install python-docx"

  doc = Document(str(path))
  content = f"Word File: {path.name}\n\n"
  for para in doc.paragraphs:
    if para.text.strip():
      content += para.text + "\n"
  return content


def _read_text(path: Path) -> str:
  with open(path, "r", encoding="utf-8") as f:
    content = f.read()
  return content
