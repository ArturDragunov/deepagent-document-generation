"""Python code execution tool for deepagents.

Allows the Reviewer agent to write and execute Python code for generating
Word documents (mimicking Claude Code's approach). Synchronous (deepagents requirement).
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from src.config import get_config


def execute_python(code: str, timeout_sec: int = 120) -> str:
  """Execute Python code and return its output.

  Writes the code to a temporary file and runs it as a subprocess.
  The code has access to python-docx and other installed packages.
  Use this to generate Word documents with precise formatting control.

  The outputs/ directory is available for saving generated files.
  Example: save a .docx file to 'outputs/BRD_final.docx'.

  Args:
      code: Python source code to execute.
      timeout_sec: Maximum execution time in seconds (default: 120).

  Returns:
      Execution result with stdout, stderr, and exit code.
  """
  config = get_config()
  output_dir = config.output_dir
  output_dir.mkdir(parents=True, exist_ok=True)

  # Write code to a temp file
  with tempfile.NamedTemporaryFile(
    mode="w",
    suffix=".py",
    delete=False,
    encoding="utf-8",
  ) as f:
    f.write(code)
    temp_path = f.name

  try:
    result = subprocess.run(
      [sys.executable, temp_path],
      capture_output=True,
      text=True,
      timeout=timeout_sec,
      cwd=os.getcwd(),
      env={**os.environ, "OUTPUT_DIR": str(output_dir)},
    )

    output = ""
    if result.stdout.strip():
      output += f"STDOUT:\n{result.stdout.strip()}\n"
    if result.stderr.strip():
      output += f"STDERR:\n{result.stderr.strip()}\n"
    output += f"EXIT CODE: {result.returncode}\n"

    if result.returncode == 0 and not output.strip():
      output = "Code executed successfully (no output).\n"

    return output

  except subprocess.TimeoutExpired:
    return f"ERROR: Code execution timed out after {timeout_sec}s"
  except Exception as e:
    return f"ERROR: Code execution failed: {e}"
  finally:
    try:
      os.unlink(temp_path)
    except OSError:
      pass
