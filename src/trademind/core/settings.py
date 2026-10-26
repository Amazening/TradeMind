"""Settings, read from environment variables and the .env file.

Secrets are only ever read here. Nothing else reads the environment.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    groq_api_key: SecretStr | None = None
    groq_model: str = "llama-3.1-8b-instant"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:14b"
    price_cache_dir: Path = Path(".cache/prices")
    explanation_cache_dir: Path = Path(".cache/explanations")


@lru_cache
def get_settings() -> Settings:
    return Settings()
