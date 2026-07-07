from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "RepoPilot API"
    environment: str = "development"
    database_url: str = "sqlite:///./repopilot.db"
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        validation_alias=AliasChoices("OPENAI_BASE_URL", "LLM_BASE_URL"),
    )
    openai_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("OPENAI_API_KEY", "LLM_API_KEY"),
    )
    openai_model: str = Field(
        default="gpt-4.1-mini",
        validation_alias=AliasChoices("OPENAI_MODEL", "LLM_MODEL_ID"),
    )
    force_llm_fallback: bool = Field(default=False, validation_alias="REPOPILOT_FORCE_LLM_FALLBACK")
    clone_base_dir: Path = Path("./.repopilot/repos")
    worktree_base_dir: Path = Path("./.repopilot/worktrees")
    max_repair_iterations: int = 2
    benchmark_dir: Path = Path("../../benchmark/cases")

    model_config = SettingsConfigDict(env_file=(".env", "../../.env"), env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
