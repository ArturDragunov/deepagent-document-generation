"""Command-line interface for BRD generation system."""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from src.config import get_config
from src.orchestrator import BRDOrchestrator
from src.models import MessageStatus


def setup_logging(log_level: str = "INFO"):
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)


async def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="DeepAgents-powered BRD Generation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.main --query "Create BRD for authentication system"
  python -m src.main --query "Document payment flow" --corpus ./data
  python -m src.main --query "API integration spec" --output ./results
        """,
    )

    parser.add_argument(
        "--query",
        type=str,
        required=True,
        help="User query for BRD generation",
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path("example_data/corpus"),
        help="Path to corpus directory (default: example_data/corpus)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs"),
        help="Output directory for results (default: outputs)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate input without running pipeline",
    )

    args = parser.parse_args()

    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)

    logger.info("=" * 80)
    logger.info("DeepAgents BRD Generation System")
    logger.info("=" * 80)

    if not args.corpus.exists():
        logger.error(f"Corpus directory not found: {args.corpus}")
        sys.exit(1)

    corpus_files = [
        str(f.relative_to(args.corpus))
        for f in args.corpus.rglob("*")
        if f.is_file()
    ]

    if not corpus_files:
        logger.warning(f"No files found in corpus: {args.corpus}")

    logger.info(f"Query: {args.query}")
    logger.info(f"Corpus directory: {args.corpus}")
    logger.info(f"Files found: {len(corpus_files)}")
    logger.info(f"Output directory: {args.output}")

    if args.dry_run:
        logger.info("Dry run - validation only")
        return

    try:
        config = get_config()
        if not config.llm_api_key:
            logger.error(f"LLM_API_KEY environment variable not set for provider '{config.llm_provider}'")
            sys.exit(1)

        logger.info("\nStarting BRD generation pipeline...\n")

        orchestrator = BRDOrchestrator()
        result = await orchestrator.run_pipeline(
            user_query=args.query,
            corpus_files=corpus_files,
            output_dir=args.output,
        )

        logger.info("\n" + "=" * 80)
        logger.info("EXECUTION SUMMARY")
        logger.info("=" * 80)

        logger.info(f"Status: {result.status.value}")
        logger.info(f"Execution time: {result.execution_time_sec:.2f}s")

        if result.warnings:
            logger.info("\nDetails:")
            for warning in result.warnings:
                logger.info(f"  • {warning}")

        if result.errors:
            logger.error("\nErrors:")
            for error in result.errors:
                logger.error(f"  • {error}")

        logger.info("=" * 80 + "\n")

        sys.exit(0 if result.status == MessageStatus.SUCCESS else 1)

    except KeyboardInterrupt:
        logger.info("Pipeline interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

