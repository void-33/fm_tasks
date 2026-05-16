from fastapi import APIRouter, HTTPException
import psycopg2

from logger import logger
from models import AIQueryRequest, PipelineResult, SQLQueryRequest, SQLQueryResult
from services.pipeline_service import run_pipeline
from services.sql_execution_service import execute_sql
from services.sql_validation_service import validate_sql

router = APIRouter(prefix="", tags=[""])


@router.post("/ai-query", response_model=PipelineResult)
def ai_query(req: AIQueryRequest):
    """Run the full Text-to-SQL pipeline for a single question."""
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    return run_pipeline(req.question.strip())


@router.post("/sql-query", response_model=SQLQueryResult)
def sql_query(req: SQLQueryRequest):
    """Execute the given query."""
    query = req.sql.strip()

    logger.info("=" * 60)
    logger.info(f"QUERY: {query}")

    if not query:
        raise HTTPException(status_code=400, detail="SQL query cannot be empty")

    validation = validate_sql(query)
    if not validation.valid:
        msg = f"Step 1 ✗ Validation failed: {validation.reason}"
        logger.warning(f"SQL Invalid: {msg}")
        return SQLQueryResult(
            sql=query,
            row_count=0,
            result=[],
            status="failed",
        )
    logger.info("Step 1 ✓ Validation passed")

    try:
        logger.info("Step 2 → Executing SQL against PostgreSQL")
        result = execute_sql(query)
        logger.info(f"Step 2 ✓  {len(result)} row(s) returned")
        status = "success"
    except (psycopg2.Error, Exception) as exec_err:
        error_msg = str(exec_err)
        logger.warning(f"Step 2 ✗  Execution failed: {error_msg}")
        status = "failed"
        result = []

    return SQLQueryResult(
        sql=query,
        row_count=len(result),
        result=result,
        status=status,
    )
