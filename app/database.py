"""Database connection and session management.

Provides a SQLAlchemy engine, session factory, and a ``get_db`` dependency
used by FastAPI endpoints to obtain request-scoped database sessions.
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    """Declarative base class for all ORM models."""


engine = create_engine(
    settings.sqlalchemy_url,
    pool_pre_ping=True,
    pool_recycle=1800,
    echo=settings.debug,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """Yield a request-scoped database session, closing it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
