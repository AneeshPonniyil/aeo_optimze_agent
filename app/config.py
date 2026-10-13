import json
from typing import List, Optional, Union
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET_FALLBACK = "dev_insecure_development_key_do_not_use_in_prod"
DEV_AUDIT_API_KEY_FALLBACK = "dev-audit-api-key"
KNOWN_DEV_SECRETS = {
    "dev_secret_key_change_in_production",
    DEV_SECRET_FALLBACK,
    "change_me",
    "secret",
}


class Settings(BaseSettings):
    PROJECT_NAME: str = "Zenvora AI Audit Copilot"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"  # development, testing, production
    DEBUG: bool = True

    # Secrets
    SECRET_KEY: Optional[str] = None
    AUDIT_API_KEY: Optional[str] = None

    # CORS Allowlist
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ]

    # Rate Limiting
    AUDIT_RATE_LIMIT_PER_MINUTE: int = 10

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

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: Union[str, List[str]]) -> List[str]:
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("[") and value.endswith("]"):
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, list):
                        return [str(o).strip() for o in parsed if str(o).strip()]
                except json.JSONDecodeError:
                    pass
            return [o.strip() for o in value.split(",") if o.strip()]
        return [str(o).strip() for o in value if str(o).strip()]

    @model_validator(mode="after")
    def validate_environment_and_secrets(self) -> "Settings":
        env = self.ENVIRONMENT.lower().strip()
        object.__setattr__(self, "ENVIRONMENT", env)

        if env == "production":
            # 1. Debug mode must never be active in production
            if self.DEBUG:
                raise ValueError("DEBUG mode must be disabled in production.")

            # 2. Secret Key validation
            if not self.SECRET_KEY or self.SECRET_KEY in KNOWN_DEV_SECRETS:
                raise ValueError(
                    "SECRET_KEY must be securely configured in production and cannot use development fallbacks."
                )
            if len(self.SECRET_KEY) < 32:
                raise ValueError("SECRET_KEY must be at least 32 characters in production.")

            # 3. Audit API Key validation
            if not self.AUDIT_API_KEY or self.AUDIT_API_KEY == DEV_AUDIT_API_KEY_FALLBACK:
                raise ValueError("AUDIT_API_KEY must be securely configured in production.")

            # 4. CORS Origins validation
            if not self.ALLOWED_ORIGINS:
                raise ValueError("ALLOWED_ORIGINS cannot be empty in production.")
            for origin in self.ALLOWED_ORIGINS:
                if origin == "*" or "*" in origin:
                    raise ValueError(
                        f"Wildcard origin '{origin}' is forbidden in production ALLOWED_ORIGINS."
                    )
        else:
            # Convenient development fallbacks
            if not self.SECRET_KEY:
                object.__setattr__(self, "SECRET_KEY", DEV_SECRET_FALLBACK)
            if not self.AUDIT_API_KEY:
                object.__setattr__(self, "AUDIT_API_KEY", DEV_AUDIT_API_KEY_FALLBACK)

        return self


settings = Settings()
