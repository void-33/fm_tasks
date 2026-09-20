import asyncio
import logging
from typing import Optional

from google import genai
from google.genai import types
from openai import AsyncOpenAI
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Clients ──────────────────────────────────────────────────────────────────

_gemini_client: Optional[genai.Client] = None
_ollama_client: Optional[AsyncOpenAI] = None


def get_gemini_client() -> Optional[genai.Client]:
    global _gemini_client
    if _gemini_client is None and settings.gemini_api_key:
        _gemini_client = genai.Client(api_key=settings.gemini_api_key)
    return _gemini_client


def get_ollama_client() -> AsyncOpenAI:
    global _ollama_client
    if _ollama_client is None:
        _ollama_client = AsyncOpenAI(
            api_key="EMPTY",
            base_url=settings.ollama_api_base,
        )
    return _ollama_client


# ── Gemini call with tenacity retry ──────────────────────────────────────────

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(Exception),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
async def _call_gemini(message: str, system_prompt: str, temperature: float) -> str:
    client = get_gemini_client()
    if not client:
        raise ValueError("GEMINI_API_KEY is not configured.")

    config = types.GenerateContentConfig(
        temperature=temperature,
        system_instruction=system_prompt,
    )

    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: client.models.generate_content(
            model=settings.gemini_model,
            contents=message,
            config=config,
        ),
    )
    if response.text is None:
        raise ValueError("Gemini returned an empty response.")
    return response.text


# ── Gemini structured call with usage metadata ────────────────────────────────

async def _call_gemini_structured(
    prompt: str, system_prompt: str, temperature: float
) -> tuple[str, dict]:
    """Call Gemini and return (text, usage_dict).

    usage_dict keys: input_tokens, output_tokens, total_tokens (all int or None).
    Never estimates silently — if SDK does not provide counts, reports None.
    Falls back to Ollama on exhausted Gemini retries and records the fallback.
    """
    client = get_gemini_client()
    if not client:
        raise ValueError("GEMINI_API_KEY is not configured.")

    config = types.GenerateContentConfig(
        temperature=temperature,
        system_instruction=system_prompt,
    )

    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=config,
        ),
    )
    if response.text is None:
        raise ValueError("Gemini returned an empty response.")

    # Extract normalized usage from SDK metadata
    usage = {"input_tokens": None, "output_tokens": None, "total_tokens": None, "provider": "gemini"}
    try:
        um = response.usage_metadata
        if um:
            usage["input_tokens"] = getattr(um, "prompt_token_count", None)
            usage["output_tokens"] = getattr(um, "candidates_token_count", None)
            t = usage["input_tokens"]
            o = usage["output_tokens"]
            usage["total_tokens"] = (t + o) if (t is not None and o is not None) else None
    except Exception:
        pass  # usage remains None values — reported as unknown, not estimated

    return response.text, usage


# ── Ollama call ───────────────────────────────────────────────────────────────

async def _call_ollama(message: str, system_prompt: str, temperature: float) -> str:
    client = get_ollama_client()
    response = await client.chat.completions.create(
        model=settings.ollama_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ],
        temperature=temperature,
    )
    return response.choices[0].message.content


async def _call_ollama_structured(
    prompt: str, system_prompt: str, temperature: float
) -> tuple[str, dict]:
    text = await _call_ollama(prompt, system_prompt, temperature)
    return text, {
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
        "provider": f"ollama/{settings.ollama_model}",
        "fallback_used": False,
    }


# ── Public interface: legacy path (unchanged) ─────────────────────────────────

async def generate_response(
    message: str,
    context: str = "",
    temperature: float = 0.7,
    model_type: str = "gemini",
) -> dict:
    """Generate a response using the primary model (Gemini) with automatic
    retry (tenacity) and graceful fallback to Ollama on exhausted retries.

    Preserved for the existing /api/v1/chat endpoint. Do not change.
    """
    system_prompt = "You are a highly capable AI assistant. Be concise and helpful."
    if context:
        system_prompt += (
            f"\n\nUse ONLY the following context to answer the user's question:\n{context}"
        )

    used_model = model_type
    fallback_used = False
    error_detail: Optional[str] = None

    if model_type == "gemini":
        try:
            reply = await _call_gemini(message, system_prompt, temperature)
        except Exception as e:
            error_detail = str(e)
            logger.error(f"Gemini exhausted retries: {error_detail}. Using Ollama fallback.")
            try:
                reply = await _call_ollama(message, system_prompt, temperature)
                fallback_used = True
                used_model = f"ollama/{settings.ollama_model} (fallback)"
            except Exception as fe:
                reply = "All models are currently unavailable. Please try again later."
                used_model = "none"
                error_detail = str(fe)
    else:
        try:
            reply = await _call_ollama(message, system_prompt, temperature)
            used_model = f"ollama/{settings.ollama_model}"
        except Exception as e:
            reply = f"Ollama error: {str(e)}"
            used_model = "none"

    return {
        "reply": reply,
        "model_used": used_model,
        "fallback_used": fallback_used,
    }


# ── Public interface: agent structured decision call ──────────────────────────

async def generate_structured_action(
    prompt: str,
    system_prompt: str,
    temperature: float = 0.2,
    model_type: str = "gemini",
) -> tuple[str, dict]:
    """Request a structured JSON action from the model.

    Returns (raw_text, usage_dict). The caller is responsible for parsing and
    validating the JSON. Falls back to Ollama on Gemini failure; records
    provider and fallback status in usage_dict.

    usage_dict keys:
      input_tokens, output_tokens, total_tokens: int | None
      provider: 'gemini' | 'ollama/<model>' | 'none'
      fallback_used: bool
    """
    if model_type == "ollama":
        return await _call_ollama_structured(prompt, system_prompt, temperature)

    try:
        text, usage = await _call_gemini_structured(prompt, system_prompt, temperature)
        usage["fallback_used"] = False
        return text, usage
    except Exception as e:
        logger.warning(f"Gemini structured call failed: {e}. Attempting Ollama fallback.")
        try:
            text = await _call_ollama(prompt, system_prompt, temperature)
            usage = {
                "input_tokens": None,
                "output_tokens": None,
                "total_tokens": None,
                "provider": f"ollama/{settings.ollama_model}",
                "fallback_used": True,
            }
            return text, usage
        except Exception as fe:
            logger.error(f"Ollama fallback also failed: {fe}")
            usage = {
                "input_tokens": None,
                "output_tokens": None,
                "total_tokens": None,
                "provider": "none",
                "fallback_used": True,
            }
            raise RuntimeError(f"All providers failed: gemini={e}; ollama={fe}") from fe


async def check_ollama_health() -> bool:
    try:
        client = get_ollama_client()
        models = await client.models.list()
        return len(models.data) > 0
    except Exception:
        return False
