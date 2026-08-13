from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ───────────────────────────────────────────────────────────────────
    APP_NAME: str = "Site Visit AI Assistant"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str
    DATABASE_URL_SYNC: str

    # ── Redis ────────────────────────────────────────────────────────────────
    REDIS_URL: str
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str

    # ── Anthropic ────────────────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str
    CLAUDE_SONNET_MODEL: str = "claude-sonnet-4-6"
    CLAUDE_OPUS_MODEL: str = "claude-opus-4-6"
    CLAUDE_MAX_TOKENS: int = 4096

    # ── OpenAI ───────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str
    GPT4_MODEL: str = "gpt-4.1"
    GPT4_MAX_TOKENS: int = 4096

    # ── Tavily ───────────────────────────────────────────────────────────────
    TAVILY_API_KEY: str

    # ── Storage (local — lưu trực tiếp trên Mac Mini) ───────────────────────────
    TMP_UPLOAD_DIR: str = "/tmp/sitevisit"
    MEDIA_DIR: str = "/data/sitevisit/photos"     # lưu vĩnh viễn, mount volume riêng
    MEDIA_URL_PREFIX: str = "/media"               # Nginx serve tại path này
    MAX_FILE_SIZE_MB: int = 20
    PROCESSED_MAX_SIZE_MB: int = 5

    @property
    def MEDIA_ROOT(self) -> Path:
        p = Path(self.MEDIA_DIR)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def MAX_FILE_SIZE_BYTES(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    @property
    def PROCESSED_MAX_SIZE_BYTES(self) -> int:
        return self.PROCESSED_MAX_SIZE_MB * 1024 * 1024

    # ── Celery ───────────────────────────────────────────────────────────────
    CELERY_TASK_TIMEOUT: int = 300
    CELERY_MAX_RETRIES: int = 3
    PHOTO_PROCESSING_QUEUE: str = "photo_processing"
    ENRICHMENT_QUEUE: str = "enrichment"

    # ── CORS ─────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:80"

    @property
    def CORS_ORIGINS(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def TMP_DIR(self) -> Path:
        p = Path(self.TMP_UPLOAD_DIR)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
