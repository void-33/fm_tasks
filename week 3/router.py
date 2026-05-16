from fastapi import APIRouter, HTTPException
import json
import psycopg2

from database import test_connection
from models import PipelineResult, AIQueryRequest, SQLQueryRequest, BenchmarkRequest, SQLQueryResult
from pipeline import run_pipeline
from validator import validate_sql
from logger import log_file,logger
from executor import execute_sql

router = APIRouter(prefix="",tags=[""])

@router.get("/health")
def health():
    db_ok = test_connection()
    return {"status": "ok", "db_connected": db_ok}

@router.post("/ai-query", response_model=PipelineResult)
def ai_query(req: AIQueryRequest):
    """Run the full Text-to-SQL pipeline for a single question."""
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    return run_pipeline(req.question.strip())

@router.post("/sql-query",response_model=SQLQueryResult)
def sql_query(req: SQLQueryRequest):
    """Execute the given query"""
    query = req.sql.strip()

    logger.info("=" * 60)
    logger.info(f"QUERY: {query}")

    if not query:
        raise HTTPException(status_code=400 ,detail="SQL query cannot be empty")
    
    validation = validate_sql(query)
    if not validation.valid:
        msg = f"Step 1 ✗ Validation failed: {validation.reason}"
        logger.warning(f"SQL Invalid: {msg}")
        return SQLQueryResult(
            sql=query,
            row_count=0,
            result=[],
            status="failed"
        )
    logger.info("Step 1 ✓ Validation passed")

    try:
        logger.info("Step 2 → Executing SQL against PostgreSQL")
        result = execute_sql(query)
        logger.info(f"Step 2 ✓  {len(result)} row(s) returned")
        status= 'success'
    except (psycopg2.Error, Exception) as exec_err:
        error_msg = str(exec_err)
        logger.warning(f"Step 2 ✗  Execution failed: {error_msg}")
        status = 'failed'
    return SQLQueryResult(
        sql=query,
        row_count = len(result),
        result=result,
        status=status
    )


@router.post("/benchmark")
def benchmark(req: BenchmarkRequest):
    """
    Run the pipeline against a list of questions and return
    an evaluation report with per-question results and summary metrics.
    """
    if not req.questions:
        raise HTTPException(status_code=400, detail="Questions list cannot be empty")

    results = []
    for q in req.questions:
        r = run_pipeline(q.strip())
        results.append(r)

    total = len(results)
    succeeded = sum(1 for r in results if r.status == "success")
    retried = sum(1 for r in results if r.retried)
    fixed = sum(1 for r in results if r.retry_fixed)
    avg_latency = int(sum(r.latency_ms for r in results) / total) if total else 0

    return {
        "summary": {
            "total_questions": total,
            "success_count": succeeded,
            "failed_count": total - succeeded,
            "success_rate_pct": round(succeeded / total * 100, 1) if total else 0,
            "retried_count": retried,
            "fixed_by_retry_count": fixed,
            "avg_latency_ms": avg_latency,
        },
        "results": [r.model_dump() for r in results],
    }


@router.get("/logs")
def get_logs(limit: int = 50):
    """Return the last N log entries from today's log file."""
    if not log_file.exists():
        return {"entries": []}
    lines = log_file.read_text().splitlines()
    json_lines = [l for l in lines if l.startswith("{")]
    parsed = []
    for line in json_lines[-limit:]:
        try:
            parsed.append(json.loads(line))
        except Exception:
            pass
    return {"entries": parsed}
