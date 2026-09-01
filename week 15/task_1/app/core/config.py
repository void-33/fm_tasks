from pathlib import Path
from typing import Optional

from dotenv import find_dotenv
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    gemini_api_key: str = ""
    vllm_api_base: str = "http://ollama:11434/v1"
    chroma_db_dir: str = "./chroma_db"
    hf_token: Optional[str] = None
    
    class Config:
        env_file = find_dotenv(usecwd=True) or str(Path(__file__).resolve().parents[3] / ".env")
        extra = "ignore"

settings = Settings()
