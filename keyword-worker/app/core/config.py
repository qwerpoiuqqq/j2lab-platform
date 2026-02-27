"""Keyword worker configuration loaded from environment variables."""

from __future__ import annotations

from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Keyword worker settings."""

    # === Application ===
    APP_NAME: str = "J2LAB Keyword Worker"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    WORKER_PORT: int = 8001

    # === Database (same PostgreSQL as api-server) ===
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "j2lab_platform"
    DB_USER: str = "j2lab"
    DB_PASSWORD: str = "change_me_to_secure_password"

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    # === Proxy (Decodo) ===
    DECODO_USERNAME: str = ""
    DECODO_PASSWORD: str = ""
    DECODO_HOST: str = "gate.decodo.com"
    DECODO_PORT: int = 10001
    DECODO_ENDPOINT_COUNT: int = 500

    # === Gemini AI (optional, for keyword classification) ===
    GEMINI_API_KEY: str = ""

    # === API Server callback URL ===
    API_SERVER_URL: str = "http://api-server:8000"

    # === Internal API Secret (for callback auth) ===
    INTERNAL_API_SECRET: str = "change_me_to_internal_secret"

    # === Worker limits ===
    MAX_CONCURRENT_JOBS: int = 3
    PLAYWRIGHT_HEADLESS: bool = True

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


settings = Settings()
