from pydantic_settings import BaseSettings

from typing import Optional

class Settings(BaseSettings):
    gemini_api_key: str = ""
    vllm_api_base: str = "http://ollama:11434/v1"
    chroma_db_dir: str = "./chroma_db"
    hf_token: Optional[str] = None
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
