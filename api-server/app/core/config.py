"""Application configuration loaded from environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    # === Application ===
    APP_NAME: str = "J2LAB Platform API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # === Database ===
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
        """Synchronous URL for Alembic migrations."""
        return (
            f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    # === JWT ===
    SECRET_KEY: str = "change_me_to_random_secret_key"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # === AES Encryption (for superap passwords) ===
    AES_ENCRYPTION_KEY: str | None = None  # Falls back to SECRET_KEY if not set

    # === Worker URLs ===
    KEYWORD_WORKER_URL: str = "http://keyword-worker:8001"
    CAMPAIGN_WORKER_URL: str = "http://campaign-worker:8002"
    API_SERVER_URL: str = "http://api-server:8000"

    # === CORS ===
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # === Settlement ===
    SETTLEMENT_SECRET_PASSWORD: str = "j2lab-settlement-2026"

    # === Internal API ===
    INTERNAL_API_SECRET: str = "change_me_to_internal_secret"

    # === Order limits ===
    ORDER_MAX_ITEMS: int = 500

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


settings = Settings()
