"""Verify connectivity to the shared PostgreSQL database.

Dairy AI consumes tables owned by the platform, so this script only checks
that the configured credentials can reach the shared database.

Usage:
    python -m scripts.run_migrations
"""

from __future__ import annotations

import logging

from sqlalchemy import text

import app.models  # noqa: F401 — register ORM models with Base.metadata
from app.database import Base, SessionLocal, engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scripts.db_check")


def run_migrations() -> None:
    """Create dairy-ai-owned tables and verify connectivity."""
    Base.metadata.create_all(bind=engine)
    logger.info("Dairy-ai tables ensured.")

    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        logger.info("Database connection verified.")
    finally:
        db.close()


if __name__ == "__main__":
    run_migrations()
