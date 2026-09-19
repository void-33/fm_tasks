from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings


def _find_shared_env_file() -> str:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / ".env"
        if candidate.is_file():
            return str(candidate)
    return ".env"


class Settings(BaseSettings):
    # ── LLM providers ─────────────────────────────────────────────────────────
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    ollama_api_base: str = "http://ollama:11434/v1"
    ollama_model: str = "qwen2.5:0.5b"

    # ── Infrastructure ────────────────────────────────────────────────────────
    redis_url: str = "redis://redis:6379"
    cache_ttl: int = 3600  # seconds (1 hour)

    rate_limit: str = "60/minute"

    chroma_db_dir: str = "./chroma_db"
    hf_token: Optional[str] = None

    # ── Agent bounded settings ────────────────────────────────────────────────
    # Maximum number of model decisions (loop iterations) per agent request.
    agent_max_steps: int = 6
    # Maximum number of retrieval (search) calls per agent request.
    agent_max_searches: int = 4
    # Maximum chunks returned per retrieval call (hard cap on top_k).
    agent_top_k_max: int = 5
    # Maximum evidence items kept in the compact ledger.
    agent_max_evidence_items: int = 12
    # Maximum total excerpt characters in the evidence ledger.
    agent_max_evidence_chars: int = 12000
    # Maximum query length accepted for a search action.
    agent_max_query_chars: int = 500
    # Per-tool-call timeout in seconds.
    agent_tool_timeout_seconds: float = 10.0
    # Total request budget in seconds (covers all iterations).
    agent_request_timeout_seconds: float = 60.0
    # How many times to attempt repairing a malformed model action per request.
    agent_max_invalid_action_repairs: int = 1

    class Config:
        env_file = _find_shared_env_file()
        extra = "ignore"


settings = Settings()
