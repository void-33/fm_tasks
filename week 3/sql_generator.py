import json
import os
import re
from pathlib import Path
from groq import Groq
from database import SCHEMA_DESCRIPTION

client = Groq()
model = "llama-3.3-70b-versatile"

PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text()


def _parse_json(raw: str) -> dict:
    """Strip markdown fences if present, then parse JSON."""
    cleaned = re.sub(r"```(?:json)?", "", raw).replace("```", "").strip()
    return json.loads(cleaned)


def generate_sql(question: str) -> dict:
    """
    Send the natural language question to model.
    Returns a dict with keys: intent, tables, columns, filters, joins, sql, explanation.
    Raises ValueError on parse failure.
    """
    system = _load_prompt("system.txt").format(schema=SCHEMA_DESCRIPTION)

    response = client.chat.completions.create(
        model=model,
        max_tokens=1024,
        temperature=0.1,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": question},
        ],
    )

    raw = response.choices[0].message.content
    result = _parse_json(raw)

    if "sql" not in result:
        raise ValueError(f"Groq response missing 'sql' key: {raw[:200]}")

    return result


def fix_sql(question: str, failed_sql: str, error_message: str) -> dict:
    """
    Ask Groq to fix a broken SQL query given the DB error message.
    Returns a dict with keys: sql, fix_explanation.
    Raises ValueError on parse failure.
    """
    prompt = _load_prompt("fix.txt").format(
        question=question,
        sql=failed_sql,
        error=error_message,
        schema=SCHEMA_DESCRIPTION,
    )

    response = client.chat.completions.create(
        model=model,
        max_tokens=1024,
        temperature=0.1,
        messages=[
            {"role": "system", "content": prompt}
        ],
    )

    raw = response.choices[0].message.content
    result = _parse_json(raw)

    if "sql" not in result:
        raise ValueError(f"Fix response missing 'sql' key: {raw[:200]}")

    return result
