from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "RepoPilot API"
    environment: str = "development"
    database_url: str = "sqlite:///./repopilot.db"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    worktree_base_dir: Path = Path("./.repopilot/worktrees")
    max_repair_iterations: int = 2
    benchmark_dir: Path = Path("../../benchmark/cases")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
