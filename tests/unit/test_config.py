"""Unit tests for application configuration."""

from __future__ import annotations

import os

import pytest

from app.config import Settings


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    """Unset environment variables that could leak into the Settings."""
    if os.getcwd().endswith("dairy-ai"):
        monkeypatch.chdir(os.path.dirname(os.getcwd()))

    def _clear(name: str) -> None:
        if name in os.environ:
            monkeypatch.delenv(name, raising=False)

    for name in ("DATABASE_URL", "DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"):
        _clear(name)


def settings(**kwargs: object) -> Settings:
    """Build Settings without reading a stray on-disk ``.env`` file."""
    return Settings(_env_file=None, **kwargs)


def test_default_database_url() -> None:
    """The default settings should produce a valid PostgreSQL URL."""
    settings_ = settings()
    expected = "postgresql+psycopg2://dairy_user:change_me@localhost:5432/dairy_db"
    assert settings_.sqlalchemy_url == expected


def test_custom_database_url() -> None:
    """Database URL should reflect overridden host/port/name values."""
    settings_ = settings(db_host="pg.example.com", db_port=5433, db_name="farm")
    assert "pg.example.com:5433/farm" in settings_.sqlalchemy_url


def test_single_database_url_override() -> None:
    """A full DATABASE_URL should win over the individual components."""
    rendered = "postgres://user:pass@host:5432/db"
    settings_ = settings(database_url=rendered)
    assert settings_.sqlalchemy_url == "postgresql+psycopg2://user:pass@host:5432/db"
