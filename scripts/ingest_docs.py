#!/usr/bin/env python3
"""
Document ingestion CLI.

Ingest a single file or a directory of documents into the RAG pipeline.

Usage:
    python scripts/ingest_docs.py --path ./docs
    python scripts/ingest_docs.py --path ./docs/setup.md --base-url https://docs.example.com
"""

import logging
import sys
from pathlib import Path

import click

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


@click.command()
@click.option(
    "--path", "-p",
    required=True,
    type=click.Path(exists=True),
    help="Path to a file or directory to ingest.",
)
@click.option(
    "--base-url", "-u",
    default="",
    help="Base URL prefix for source citations (e.g., https://docs.example.com).",
)
def main(path: str, base_url: str):
    """Ingest documents into the Ask My Docs RAG pipeline."""
    from src.pipeline import pipeline

    target = Path(path)

    logger.info(f"Initializing pipeline...")
    pipeline.initialize()

    if target.is_file():
        logger.info(f"Ingesting file: {target}")
        result = pipeline.ingest_file(target, base_url=base_url)
        logger.info(f"Done: {result}")
    elif target.is_dir():
        logger.info(f"Ingesting directory: {target}")
        results = pipeline.ingest_directory(target, base_url=base_url)
        total_chunks = sum(r.get("chunks", 0) for r in results)
        logger.info(f"Done: {len(results)} files, {total_chunks} total chunks.")
        for r in results:
            status = f"{r.get('chunks', 0)} chunks" if "chunks" in r else f"ERROR: {r.get('error')}"
            name = r.get("title", r.get("file", "unknown"))
            logger.info(f"  {name}: {status}")
    else:
        logger.error(f"Path is neither a file nor directory: {target}")
        sys.exit(1)


if __name__ == "__main__":
    main()
