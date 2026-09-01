import os
import asyncio
import logging
import hashlib
from typing import Optional

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Reliability & Performance imports
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from cachetools import TTLCache

import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Setup Rate Limiting ---
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Production AI Backend")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Setup Prompt/Response Caching ---
# Caches up to 1000 items, expires after 1 hour (3600 seconds)
# In a large production app, this would be Redis/Memcached.
response_cache = TTLCache(maxsize=1000, ttl=3600)

# --- Configure API ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    logger.warning("GEMINI_API_KEY not set. API will not function.")

# Models Configuration
PRIMARY_MODEL = "gemini-2.0-pro-exp-02-05"
FALLBACK_MODEL = "gemini-2.5-flash"  # Faster, more reliable fallback

class ChatRequest(BaseModel):
    query: str = Field(..., description="The user's input/question")
    use_cache: bool = Field(default=True, description="Whether to use the prompt cache")

class ChatResponse(BaseModel):
    response: str
    model_used: str
    cached: bool

def generate_cache_key(query: str) -> str:
    """Generate a consistent hash for the prompt."""
    return hashlib.md5(query.lower().strip().encode()).hexdigest()

# --- Retry Mechanism ---
# Retry up to 3 times, with exponential backoff (wait 2, 4, 8 seconds)
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((Exception,)),  # Retry on any exception for demonstration
    reraise=True
)
async def call_llm_with_retry(model_name: str, prompt: str) -> str:
    """Make the API call to LLM with async capabilities and tenacity retries."""
    logger.info(f"Attempting to call {model_name}...")

    # Offload the synchronous SDK call to an async threadpool to not block the FastAPI event loop
    loop = asyncio.get_event_loop()

    model = genai.GenerativeModel(model_name)
    response = await loop.run_in_executor(None, model.generate_content, prompt)

    if not response.text:
         raise ValueError("Empty response from model")

    return response.text

async def get_ai_response(prompt: str) -> tuple[str, str]:
    """Handles Graceful Degradation / Fallback logic."""
    try:
        # Try primary model first
        response_text = await call_llm_with_retry(PRIMARY_MODEL, prompt)
        return response_text, PRIMARY_MODEL
    except Exception as primary_err:
        logger.warning(f"Primary model ({PRIMARY_MODEL}) failed: {primary_err}. Initiating fallback...")
        try:
            # Fallback to secondary model if primary fails
            response_text = await call_llm_with_retry(FALLBACK_MODEL, prompt)
            return response_text, FALLBACK_MODEL
        except Exception as fallback_err:
            logger.error(f"Fallback model ({FALLBACK_MODEL}) also failed: {fallback_err}")
            raise HTTPException(status_code=503, detail="Service Unavailable. AI providers failed.")


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "production-ai-backend"}

# --- Process Concurrent / Async Requests ---
@app.post("/api/chat", response_model=ChatResponse)
@limiter.limit("10/minute") # Rate limiting: 10 requests per minute per IP
async def chat_endpoint(request: Request, body: ChatRequest):
    """
    Production chat endpoint featuring:
    1. Async Request Handling
    2. Prompt/Response Caching
    3. Rate Limiting (via slowapi limiter)
    4. Fallback Execution (via get_ai_response)
    5. Automatic Retries (via tenacity on the LLM call)
    """
    # 1. Caching
    cache_key = generate_cache_key(body.query)
    if body.use_cache and cache_key in response_cache:
        logger.info(f"Cache hit for query: '{body.query[:20]}...'")
        cached_data = response_cache[cache_key]
        return ChatResponse(
            response=cached_data["response"],
            model_used=cached_data["model_used"],
            cached=True
        )

    # 2. Process with Retries, Async, and Fallback
    try:
        logger.info(f"Processing chat request asynchronously...")
        response_text, model_used = await get_ai_response(body.query)

        # Save to cache
        response_cache[cache_key] = {
            "response": response_text,
            "model_used": model_used
        }

        return ChatResponse(
            response=response_text,
            model_used=model_used,
            cached=False
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error handling request: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
