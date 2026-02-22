from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


# 프로젝트 루트 디렉토리 계산
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend의 상위 = 프로젝트 루트
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )

    # App
    SECRET_KEY: str = "change-this-secret-key"
    DEBUG: bool = True

    # Database (절대 경로 사용)
    DATABASE_URL: str = f"sqlite:///{DATA_DIR / 'quantum.db'}"

    # CORS (환경변수: 쉼표 구분 문자열, 예: "https://a.com,https://b.com")
    CORS_ORIGINS: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        """CORS 허용 오리진 목록 반환."""
        defaults = ["http://localhost:3000", "http://127.0.0.1:3000"]
        if self.CORS_ORIGINS:
            extra = [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]
            return defaults + extra
        return defaults



settings = Settings()
