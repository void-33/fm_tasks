import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg2
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import test_connection
from executor import execute_sql
from sql_generator import fix_sql, generate_sql
from validator import validate_sql

# ── Logging ──────────────────────────────────────────────────────────────────

LOGS_DIR = Path(__file__).parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

log_file = LOGS_DIR / f"pipeline_{datetime.now().strftime('%Y%m%d')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("text2sql")

# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="Text-to-SQL Pipeline",
    description="Natural language → SQL → PostgreSQL execution with auto-retry",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request / Response models ─────────────────────────────────────────────────


class QueryRequest(BaseModel):
    question: str


class BenchmarkRequest(BaseModel):
    questions: list[str]


class PipelineResult(BaseModel):
    question: str
    decomposition: dict | None
    sql: str
    result: list[dict]
    status: str                    # "success" | "failed"
    retried: bool
    retry_fixed: bool
    error: str | None
    fix_explanation: str | None
    latency_ms: int


# ── Core pipeline ─────────────────────────────────────────────────────────────


def run_pipeline(question: str) -> PipelineResult:
    start = time.time()
    logger.info("=" * 60)
    logger.info(f"QUESTION: {question}")

    decomposition: dict | None = None
    sql = ""
    result: list[dict] = []
    status = "success"
    retried = False
    retry_fixed = False
    error_msg: str | None = None
    fix_explanation: str | None = None

    # ── Step 1: Generate SQL via LLM ──────────────────────────────────────────
    try:
        logger.info("Step 1 → Calling Groq for decomposition + SQL generation")
        decomposition = generate_sql(question)
        sql = decomposition["sql"]
        logger.info(f"Step 1 ✓  SQL: {sql}")
    except Exception as e:
        logger.error(f"Step 1 ✗  Generation failed: {e}")
        latency = int((time.time() - start) * 1000)
        _write_log(question, "", [], "failed", str(e), latency)
        return PipelineResult(
            question=question, decomposition=None, sql="",
            result=[], status="failed", retried=False, retry_fixed=False,
            error=str(e), fix_explanation=None, latency_ms=latency,
        )

    # ── Step 2: Validate (safety check) ──────────────────────────────────────
    validation = validate_sql(sql)
    if not validation.valid:
        msg = f"Validation failed: {validation.reason}"
        logger.warning(f"Step 2 ✗  {msg}")
        latency = int((time.time() - start) * 1000)
        _write_log(question, sql, [], "failed", msg, latency)
        return PipelineResult(
            question=question, decomposition=decomposition, sql=sql,
            result=[], status="failed", retried=False, retry_fixed=False,
            error=msg, fix_explanation=None, latency_ms=latency,
        )
    logger.info("Step 2 ✓  Validation passed")

    # ── Step 3: Execute ───────────────────────────────────────────────────────
    try:
        logger.info("Step 3 → Executing SQL against PostgreSQL")
        result = execute_sql(sql)
        logger.info(f"Step 3 ✓  {len(result)} row(s) returned")
    except (psycopg2.Error, Exception) as exec_err:
        error_msg = str(exec_err)
        logger.warning(f"Step 3 ✗  Execution failed: {error_msg}")

        # ── Step 4: Auto-fix + retry (max 1) ─────────────────────────────────
        retried = True
        logger.info("Step 4 → Auto-fix: asking Groq to correct the SQL")
        try:
            fix = fix_sql(question, sql, error_msg)
            fixed_sql = fix["sql"]
            fix_explanation = fix.get("fix_explanation", "")
            logger.info(f"Step 4   Fixed SQL: {fixed_sql}")
            logger.info(f"Step 4   Fix reason: {fix_explanation}")

            fix_validation = validate_sql(fixed_sql)
            if not fix_validation.valid:
                raise ValueError(f"Fixed SQL failed validation: {fix_validation.reason}")

            result = execute_sql(fixed_sql)
            sql = fixed_sql
            retry_fixed = True
            status = "success"
            logger.info(f"Step 4 ✓  Retry succeeded — {len(result)} row(s)")
        except Exception as retry_err:
            error_msg = str(retry_err)
            status = "failed"
            logger.error(f"Step 4 ✗  Retry also failed: {error_msg}")

    latency = int((time.time() - start) * 1000)
    logger.info(f"DONE  status={status}  retried={retried}  latency={latency}ms")
    _write_log(question, sql, result, status, error_msg, latency)

    return PipelineResult(
        question=question,
        decomposition=decomposition,
        sql=sql,
        result=result,
        status=status,
        retried=retried,
        retry_fixed=retry_fixed,
        error=error_msg if status == "failed" else None,
        fix_explanation=fix_explanation,
        latency_ms=latency,
    )


def _write_log(question: str, sql: str, result: list, status: str, error: Any, latency: int):
    """Append a JSON log entry to today's log file."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "question": question,
        "sql": sql,
        "row_count": len(result),
        "status": status,
        "error": error,
        "latency_ms": latency,
    }
    with open(log_file, "a") as f:
        f.write(json.dumps(entry) + "\n")


# ── API routes ────────────────────────────────────────────────────────────────


@app.get("/health")
def health():
    db_ok = test_connection()
    return {"status": "ok", "db_connected": db_ok}


@app.post("/query", response_model=PipelineResult)
def query(req: QueryRequest):
    """Run the full Text-to-SQL pipeline for a single question."""
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    return run_pipeline(req.question.strip())


@app.post("/benchmark")
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


@app.get("/logs")
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
