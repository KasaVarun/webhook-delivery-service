from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/webhooks"
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: str = "INFO"
    webhook_timeout_seconds: float = Field(default=10.0, gt=0)
    max_delivery_attempts: int = Field(default=4, ge=1)

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        return value.upper()


@lru_cache
def get_settings() -> Settings:
    return Settings()