"""Application settings loaded from environment variables and `.env`."""
from __future__ import annotations
from functools import lru_cache
from typing import Optional
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load values from `.env` when available.
# Environment variables from the shell still take priority.
load_dotenv(override=False)

class Settings(BaseSettings):
    """Typed settings model for database, model, and app configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database settings
    postgres_db: str = Field(default="", alias="POSTGRES_DB")
    postgres_user: str = Field(default="postgres", alias="POSTGRES_USER")
    postgres_password: str = Field(default="", alias="POSTGRES_PASSWORD")
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    database_url: Optional[str] = Field(default=None, alias="DATABASE_URL")

    # LLM settings
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    groq_model: str = Field(default="llama-3.3-70b-versatile", alias="GROQ_MODEL")
    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        alias="OPENROUTER_BASE_URL",
    )

    # App runtime settings
    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="info", alias="LOG_LEVEL")

    @property
    def sqlalchemy_url(self) -> str:
        """Use `DATABASE_URL` when present, otherwise build one from `POSTGRES_*`."""
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return one cached settings object per process."""
    return Settings()

settings = get_settings()
