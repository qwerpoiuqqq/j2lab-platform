"""Campaign worker configuration loaded from environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Campaign worker settings."""

    # === Application ===
    APP_NAME: str = "J2LAB Campaign Worker"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    WORKER_PORT: int = 8002

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

    @property
    def DATABASE_URL_SYNC(self) -> str:
        """Synchronous database URL for APScheduler jobs."""
        return (
            f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    # === Encryption (same key as api-server) ===
    SECRET_KEY: str = "change-this-secret-key"

    # === API Server callback URL ===
    API_SERVER_URL: str = "http://api-server:8000"

    # === Internal API Secret (for callback auth) ===
    INTERNAL_API_SECRET: str = "change_me_to_internal_secret"

    # === Landing/Redirect ===
    LANDING_BASE_URL: str = "https://logic-lab.kr"

    # === Playwright ===
    PLAYWRIGHT_HEADLESS: bool = True

    # === DRY_RUN: true면 superap.io 실제 조작 안 함 (폼 제출/키워드 변경 스킵) ===
    DRY_RUN: bool = True

    # === Scheduler ===
    ROTATION_INTERVAL_MINUTES: int = 10

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


settings = Settings()
