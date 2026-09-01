import json
import logging
import os
import tempfile

import PyPDF2
from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from typing import Optional

from app.core.cache import get_cached, make_cache_key, set_cached, check_redis_health
from app.core.limiter import limiter
from app.services.llm import generate_response, check_ollama_health
from app.services import rag

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., description="User message")
    model_type: str = Field(default="gemini", description="'gemini' or 'ollama'")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    use_rag: bool = Field(default=True)


class ChatResponse(BaseModel):
    reply: str
    model_used: str
    fallback_used: bool
    cache_hit: bool
    sources: Optional[list] = None


class IngestTextRequest(BaseModel):
    text: str
    source_name: str = "manual"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/health")
async def health():
    redis_ok = await check_redis_health()
    ollama_ok = await check_ollama_health()
    return {
        "status": "healthy",
        "redis": "up" if redis_ok else "down",
        "ollama": "up" if ollama_ok else "down",
    }


@router.post("/chat", response_model=ChatResponse)
@limiter.limit("60/minute")
async def chat(request: Request, body: ChatRequest):
    # ── 1. Check cache ─────────────────────────────────────────────────────
    cache_payload = body.model_dump()
    cache_key = make_cache_key(cache_payload)
    cached = await get_cached(cache_key)
    if cached:
        logger.info(f"Cache HIT for key={cache_key[:12]}...")
        data = json.loads(cached)
        data["cache_hit"] = True
        return ChatResponse(**data)

    # ── 2. Retrieve RAG context ────────────────────────────────────────────
    context = ""
    sources = []
    if body.use_rag:
        try:
            context, sources = await rag.retrieve_context(body.message)
        except Exception as e:
            logger.warning(f"RAG retrieval failed: {e}")

    # ── 3. Generate response (with retry + fallback inside) ────────────────
    try:
        result = await generate_response(
            message=body.message,
            context=context,
            temperature=body.temperature,
            model_type=body.model_type,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    result["sources"] = sources
    result["cache_hit"] = False

    # ── 4. Store in cache ──────────────────────────────────────────────────
    await set_cached(cache_key, json.dumps(result))

    return ChatResponse(**result)


@router.post("/ingest/text")
async def ingest_text(body: IngestTextRequest, background_tasks: BackgroundTasks):
    """Ingest raw text in the background."""
    background_tasks.add_task(rag.ingest_text, body.text, body.source_name)
    return {"status": "accepted", "message": "Text ingestion started in background."}


@router.post("/ingest/file")
async def ingest_file(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Upload and ingest a PDF or TXT file in the background."""
    try:
        content = ""
        if file.filename.endswith(".pdf"):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(await file.read())
                tmp_path = tmp.name
            with open(tmp_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        content += text + "\n"
            os.unlink(tmp_path)
        else:
            raw = await file.read()
            content = raw.decode("utf-8")

        if not content.strip():
            raise HTTPException(status_code=400, detail="File has no readable content.")

        background_tasks.add_task(rag.ingest_text, content, file.filename)
        return {"status": "accepted", "filename": file.filename}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
