import json
import time
from datetime import datetime
from typing import Any

import psycopg2

from logger import logger, log_file
from models import PipelineResult
from services.llm_sql_service import fix_sql, generate_sql
from services.sql_execution_service import execute_sql
from services.sql_validation_service import validate_sql


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

    try:
        logger.info("Step 1 → Calling Groq for decomposition + SQL generation")
        decomposition = generate_sql(question)
        sql = decomposition["sql"]
        logger.info(f"Step 1 ✓  SQL: {sql}")
    except Exception as exc:
        logger.error(f"Step 1 ✗  Generation failed: {exc}")
        latency = int((time.time() - start) * 1000)
        _write_log(question, "", [], "failed", str(exc), latency)
        return PipelineResult(
            question=question,
            decomposition=None,
            sql="",
            result=[],
            status="failed",
            retried=False,
            retry_fixed=False,
            error=str(exc),
            fix_explanation=None,
            latency_ms=latency,
        )

    validation = validate_sql(sql)
    if not validation.valid:
        msg = f"Validation failed: {validation.reason}"
        logger.warning(f"Step 2 ✗  {msg}")
        latency = int((time.time() - start) * 1000)
        _write_log(question, sql, [], "failed", msg, latency)
        return PipelineResult(
            question=question,
            decomposition=decomposition,
            sql=sql,
            result=[],
            status="failed",
            retried=False,
            retry_fixed=False,
            error=msg,
            fix_explanation=None,
            latency_ms=latency,
        )
    logger.info("Step 2 ✓  Validation passed")

    try:
        logger.info("Step 3 → Executing SQL against PostgreSQL")
        result = execute_sql(sql)
        logger.info(f"Step 3 ✓  {len(result)} row(s) returned")
    except (psycopg2.Error, Exception) as exec_err:
        error_msg = str(exec_err)
        logger.warning(f"Step 3 ✗  Execution failed: {error_msg}")

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
                raise ValueError(
                    f"Fixed SQL failed validation: {fix_validation.reason}"
                )

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
    entry = {
        "timestamp": datetime.now().isoformat(),
        "question": question,
        "sql": sql,
        "row_count": len(result),
        "status": status,
        "error": error,
        "latency_ms": latency,
    }
    with open(log_file, "a") as handle:
        handle.write(json.dumps(entry) + "\n")
