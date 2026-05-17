import logging
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .database import fetch_schema
from .agent import run_agent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent_api")

app = FastAPI(title="LangGraph Agentic SQL API")

class SQLRequest(BaseModel):
    question: str

class SQLResponse(BaseModel):
    sql: str
    result: Any
    summary: str
    status: str

def _make_json_safe(obj: Any) -> Any:
    if isinstance(obj, list):
        return [_make_json_safe(item) for item in obj]
    if isinstance(obj, dict):
        return {key: _make_json_safe(value) for key, value in obj.items()}
    from decimal import Decimal
    from datetime import datetime, date
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return obj

@app.post("/agent/sql", response_model=SQLResponse)
def agent_sql(request: SQLRequest):
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    try:
        schema_text = fetch_schema()
    except Exception as e:
        logger.warning(f"Failed to fetch schema: {e}")
        schema_text = ""

    try:
        final_state = run_agent(question, schema_text)
    except Exception as e:
        logger.error(f"Agent failed: {e}")
        raise HTTPException(status_code=500, detail="Agent execution failed.")

    final_status = "success" if final_state.get("status") == "success" else "error"
    safe_result = _make_json_safe(final_state.get("result", [])) if final_status == "success" else []

    if final_status != "success":
        summary = f"Failed to execute query after {final_state.get('retries', 0)} retries. Last error: {final_state.get('error', 'Unknown error')}"
    else:
        summary = final_state.get("summary", "Summary not generated.")

    return SQLResponse(
        sql=final_state.get("sql", ""),
        result=safe_result,
        summary=summary,
        status=final_status
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
