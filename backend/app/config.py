from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/k-shorts.db"
    ollama_host: str = "http://localhost:11434"
    data_dir: Path = Path("./data")
    default_llm_model: str = "qwen3:8b"

    youtube_client_secrets: Path = Path("./client_secret.json")
    youtube_token_file: Path = Path("./token.json")


settings = Settings()
