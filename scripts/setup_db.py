#!/usr/bin/env python3
"""
Database setup script.

Creates the pgvector extension and all required tables.
Run this once after starting your Postgres container:

    docker-compose up -d
    python scripts/setup_db.py
"""

import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db import create_tables, get_chunk_count

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    logger.info("Creating database tables...")
    try:
        create_tables()
        count = get_chunk_count()
        logger.info(f"Database ready. Current chunk count: {count}")
    except Exception as e:
        logger.error(f"Database setup failed: {e}")
        logger.error(
            "Make sure PostgreSQL is running: docker-compose up -d"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
