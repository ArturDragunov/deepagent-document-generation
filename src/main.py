"""CLI entry point for BRD generation system."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from src.config import get_config
from src.logger import get_logger
from src.orchestrator import BRDOrchestrator
from src.models import MessageStatus

logger = get_logger(__name__)


async def main():
  """Main CLI entry point."""
  parser = argparse.ArgumentParser(
    description="DeepAgents BRD Generation",
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog="""
Examples:
  python -m src.main --query "Create BRD for LC0070 authentication system"
  python -m src.main --query "Document payment flow" --corpus ./data
    """,
  )

  parser.add_argument(
    "--query", type=str, required=True,
    help="User query for BRD generation",
  )
  parser.add_argument(
    "--corpus", type=Path, default=None,
    help="Path to corpus directory (default: from config / CORPUS_DIR env)",
  )
  parser.add_argument(
    "--output", type=Path, default=None,
    help="Output directory (default: from config / OUTPUT_DIR env)",
  )
  parser.add_argument(
    "--dry-run", action="store_true",
    help="Validate input without running pipeline",
  )

  args = parser.parse_args()
  config = get_config()

  corpus_dir = args.corpus or config.corpus_dir
  output_dir = args.output or config.output_dir

  logger.info("brd_system_start", query=args.query[:200])

  if not corpus_dir.exists():
    logger.error("corpus_not_found", path=str(corpus_dir))
    sys.exit(1)

  corpus_files = [
    str(f.relative_to(corpus_dir))
    for f in corpus_dir.rglob("*")
    if f.is_file() and f.parent != corpus_dir
  ]

  logger.info("corpus_scanned", files=len(corpus_files), path=str(corpus_dir))

  if args.dry_run:
    logger.info("dry_run_complete")
    return

  try:
    orchestrator = BRDOrchestrator()
    result = await orchestrator.run_pipeline(
      user_query=args.query,
      corpus_files=corpus_files,
      output_dir=output_dir,
    )

    logger.info(
      "pipeline_result",
      status=result.status.value,
      execution_time=round(result.execution_time_sec, 2),
      messages=len(result.all_messages),
    )
    summary = result.token_summary or {}
    logger.info(
      "token_summary",
      total_input_tokens=summary.get("total_input_tokens", 0),
      total_output_tokens=summary.get("total_output_tokens", 0),
      total_cost_estimate=summary.get("total_cost_estimate", 0),
    )

    if config.generate_brd_report:
      report = {
        "tokens_used": summary.get("total_estimated_tokens", 0),
        "cost_estimate": summary.get("total_cost_estimate", 0),
        "files_included": corpus_files,
        "warnings": result.warnings,
        "execution_id": result.execution_id,
        "status": result.status.value,
        "execution_time_sec": round(result.execution_time_sec, 2),
      }
      report_path = output_dir / "brd_report.json"

      def _write_report() -> None:
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

      try:
        await asyncio.to_thread(_write_report)
        logger.info("report_written", path=str(report_path))
      except Exception as e:
        logger.warning("report_write_failed", path=str(report_path), error=str(e))

    if result.warnings:
      for w in result.warnings:
        logger.warning("pipeline_warning", detail=w)

    if result.errors:
      for e in result.errors:
        logger.error("pipeline_error", detail=e)

    sys.exit(0 if result.status == MessageStatus.SUCCESS else 1)

  except KeyboardInterrupt:
    logger.info("pipeline_interrupted")
    sys.exit(130)
  except Exception as e:
    logger.error("fatal_error", error=str(e))
    sys.exit(1)


if __name__ == "__main__":
  asyncio.run(main())
