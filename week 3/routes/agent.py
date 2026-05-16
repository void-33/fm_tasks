from fastapi import APIRouter, HTTPException

from models import AgentSQLRequest, AgentSQLResponse
from services.agent_sql_service import run_agent_sql

router = APIRouter(prefix="", tags=[""])


@router.post("/agent/sql", response_model=AgentSQLResponse)
def agent_sql(req: AgentSQLRequest):
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    return run_agent_sql(question)
