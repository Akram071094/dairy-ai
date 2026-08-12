"""Verify connectivity to the shared PostgreSQL database.

Dairy AI consumes tables owned by the platform, so this script only checks
that the configured credentials can reach the shared database.

Usage:
    python -m scripts.run_migrations
"""

from __future__ import annotations

import logging

from sqlalchemy import text

from app.database import SessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scripts.db_check")


def check_database() -> None:
    """Open a session and run a trivial query to verify connectivity."""
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        logger.info("Database connection verified.")
    finally:
        db.close()


if __name__ == "__main__":
    check_database()
