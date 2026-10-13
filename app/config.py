from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Zenvora AI Audit Copilot"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "dev_secret_key_change_in_production"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./zenvora_audit.db"

    # LLM Configuration
    LLM_PROVIDER: str = "mock"  # options: mock, openai, gemini
    OPENAI_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None

    # Crawler Configuration
    CRAWLER_MAX_TIMEOUT_SECONDS: int = 10
    CRAWLER_MAX_BODY_SIZE_BYTES: int = 5242880  # 5 MB
    CRAWLER_USER_AGENT: str = "ZenvoraAEOCopilot/1.0 (+https://zenvora.ai/bot)"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
