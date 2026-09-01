from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"

    ollama_api_base: str = "http://ollama:11434/v1"
    ollama_model: str = "qwen2.5:0.5b"

    redis_url: str = "redis://redis:6379"
    cache_ttl: int = 3600  # seconds (1 hour)

    rate_limit: str = "60/minute"

    chroma_db_dir: str = "./chroma_db"
    hf_token: Optional[str] = None

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
