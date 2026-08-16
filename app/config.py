"""Application configuration and settings management.

Settings are loaded from environment variables, optionally backed by a
``.env`` file. All values in :data:`app.config.settings` are frozen at
import time.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = "Dairy AI Services"
    api_prefix: str = "/api/v1"
    debug: bool = False
    app_env: str = "development"

    # Database connection settings
    database_url: str | None = None
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "dairy_db"
    db_user: str = "dairy_user"
    db_password: str = "change_me"

    # Backend (dairy-backend) integration for agent tool execution
    backend_base_url: str = "http://127.0.0.1:8000"
    backend_user: str = "agent@dairy.ai"
    backend_password: str = "change_me"
    backend_login_path: str = "/api/v1/auth/login"
    backend_refresh_path: str = "/api/v1/auth/refresh"
    backend_me_path: str = "/api/v1/auth/me"
    backend_authz_path: str = "/api/v1/resolve/authorization/batch"
    agent_tool_timeout: int = 30
    agent_tool_max_retries: int = 3

    # Forwarded-user authentication (frontend JWT validation)
    # When set, only forwarded users from this organization may use the
    # Action Center. Leave empty to accept any valid dairy-backend user.
    service_org_id: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def sqlalchemy_url(self) -> str:
        """Return a SQLAlchemy-compatible PostgreSQL connection URL.

        Prefers a single ``DATABASE_URL`` (Render/Supabase style) and falls
        back to the individual ``DB_*`` components.
        """
        url = self.database_url or (
            f"postgresql+psycopg2://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )
        if url.startswith("postgres://") or url.startswith("postgresql://"):
            url = "postgresql+psycopg2://" + url.split("://", 1)[1]
        return url


@lru_cache
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance."""
    return Settings()


settings = get_settings()
