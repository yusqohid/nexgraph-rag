"""Application configuration loaded from environment variables and .env."""

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6379/0"
    LLM_API_KEY: SecretStr = SecretStr("")
    LLM_MODEL: str = "gemini-2.5-flash"
    EMBEDDING_MODEL: str = "gemini-embedding-001"
    EMBEDDING_DIM: int = Field(default=1536, ge=1536, le=1536)


settings = Settings()
