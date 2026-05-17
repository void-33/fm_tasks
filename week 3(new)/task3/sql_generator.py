import json
import os
import re
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")
SYSTEM_PROMPT = "You are a careful PostgreSQL assistant."
MODEL_NAME = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

_CLIENT: Optional[Groq] = None


def _load_prompt(name: str) -> str:
    path = os.path.join(PROMPTS_DIR, name)
    with open(path, "r", encoding="utf-8") as file:
        return file.read()


def _client() -> Groq:
    global _CLIENT
    if _CLIENT is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("Missing GROQ_API_KEY in environment.")
        _CLIENT = Groq(api_key=api_key)
    return _CLIENT


def _call_llm(prompt: str, temperature: float = 0.0, max_tokens: int = 1024) -> str:
    response = _client().chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    content = response.choices[0].message.content or ""
    return content.strip()


def _strip_code_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned).strip()
    cleaned = re.sub(r"^sql\s*:\s*", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def _parse_json(text: str) -> Dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    raise ValueError("LLM response did not contain valid JSON.")


def _normalize_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        text = value.strip()
        if not text or text.lower() in {"none", "null"}:
            return []
        return [item.strip() for item in text.split(",") if item.strip()]
    return [str(value).strip()]


def _normalize_columns(value: Any) -> List[str]:
    items = _normalize_list(value)
    if not items:
        return ["*"]
    if len(items) == 1:
        text = items[0].strip().lower()
        if text in {"*", "all", "all (*)", "all columns", "all(*)"}:
            return ["*"]
    return items


def _normalize_decomposition(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "intent": str(data.get("Intent", "")).strip(),
        "tables": _normalize_list(data.get("Tables involved")),
        "columns": _normalize_columns(data.get("Columns needed")),
        "filters": _normalize_list(data.get("Filters/conditions")),
        "joins": _normalize_list(data.get("Joins")),
    }


def generate_decomposition(question: str, schema_text: Optional[str] = None) -> Dict[str, Any]:
    prompt = _load_prompt("decomposition_prompt.txt").format(
        schema=schema_text or "None",
        question=question,
    )
    raw = _call_llm(prompt, temperature=0.0, max_tokens=1024)
    data = _parse_json(raw)
    norm_data = _normalize_decomposition(data)
    return _normalize_decomposition(data)


def generate_sql(
    question: str,
    decomposition: Dict[str, Any],
    schema_text: Optional[str] = None,
) -> str:
    prompt = _load_prompt("sql_prompt.txt").format(
        schema=schema_text or "None",
        question=question,
        decomposition=json.dumps(decomposition, ensure_ascii=True, indent=2),
    )
    raw = _call_llm(prompt, temperature=0.0, max_tokens=700)
    return _strip_code_fences(raw)


def fix_sql(
    question: str,
    decomposition: Dict[str, Any],
    sql: str,
    error: str,
    schema_text: Optional[str] = None,
) -> str:
    prompt = _load_prompt("fix_prompt.txt").format(
        schema=schema_text or "None",
        question=question,
        decomposition=json.dumps(decomposition, ensure_ascii=True, indent=2),
        sql=sql,
        error=error,
    )
    raw = _call_llm(prompt, temperature=0.0, max_tokens=700)
    return _strip_code_fences(raw)
