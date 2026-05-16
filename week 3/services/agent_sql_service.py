import time
from typing import Any

import psycopg2

from logger import logger
from models import AgentSQLResponse
from services.llm_sql_service import fix_sql, generate_sql
from services.sql_execution_service import execute_sql
from services.sql_validation_service import validate_sql

MAX_ATTEMPTS = 3


def run_agent_sql(question: str) -> AgentSQLResponse:
    start = time.time()
    logger.info("=" * 60)
    logger.info(f"AGENT QUESTION: {question}")

    try:
        logger.info("Step 1 -> Understanding query")
        decomposition = generate_sql(question)
        intent = decomposition.get("intent")
        tables = decomposition.get("tables")
        columns = decomposition.get("columns")
        logger.info(
            f"Step 1 OK intent={intent} tables={tables} columns={columns}"
        )
        sql = decomposition.get("sql", "")
    except Exception as exc:
        logger.error(f"Step 1 FAIL Failed to understand query: {exc}")
        summary = "Failed to generate SQL for the question."
        return AgentSQLResponse(
            sql="",
            result=None,
            summary=summary,
            status="failed",
        )

    logger.info("Step 2 -> SQL generation")
    logger.info(f"Step 2 OK SQL: {sql}")

    result_rows: list[dict] = []
    status = "failed"
    error_msg: str | None = None

    attempt = 1
    while attempt <= MAX_ATTEMPTS:
        validation = validate_sql(sql)
        if not validation.valid:
            error_msg = f"Validation failed: {validation.reason}"
            logger.warning(f"Step 2 FAIL {error_msg}")
            logger.info("Step 3 FAIL Execution skipped (0 ms) due to validation error")
        else:
            try:
                logger.info(
                    f"Step 3 -> Executing SQL (attempt {attempt}/{MAX_ATTEMPTS})"
                )
                exec_start = time.time()
                result_rows = execute_sql(sql)
                exec_ms = int((time.time() - exec_start) * 1000)
                logger.info(
                    f"Step 3 OK {len(result_rows)} row(s) in {exec_ms} ms"
                )
                status = "success"
                break
            except (psycopg2.Error, Exception) as exec_err:
                exec_ms = int((time.time() - exec_start) * 1000)
                error_msg = str(exec_err)
                logger.warning(
                    f"Step 3 FAIL Execution failed after {exec_ms} ms: {error_msg}"
                )

        if attempt >= MAX_ATTEMPTS:
            break

        logger.info("Step 4 -> Auto-fix SQL based on error and retry")
        try:
            fix = fix_sql(question, sql, error_msg or "Unknown error")
            sql = fix.get("sql", "")
            fix_explanation = fix.get("fix_explanation")
            if fix_explanation:
                logger.info(f"Step 4   Fix reason: {fix_explanation}")
            logger.info(f"Step 4   New SQL: {sql}")
        except Exception as fix_err:
            error_msg = str(fix_err)
            logger.error(f"Step 4 FAIL Failed to fix SQL: {error_msg}")
            break

        attempt += 1

    result_value = _extract_result_value(result_rows)
    summary = _build_summary(
        explanation=decomposition.get("explanation"),
        result_value=result_value,
        row_count=len(result_rows),
        status=status,
        attempts=attempt,
    )

    total_ms = int((time.time() - start) * 1000)
    logger.info(
        f"DONE status={status} attempts={attempt} latency={total_ms}ms"
    )

    return AgentSQLResponse(
        sql=sql,
        result=result_value if status == "success" else None,
        summary=summary,
        status=status,
    )


def _extract_result_value(rows: list[dict]) -> Any:
    if len(rows) == 1:
        row = rows[0]
        if len(row) == 1:
            return next(iter(row.values()))
        return row
    return rows


def _build_summary(
    *,
    explanation: str | None,
    result_value: Any,
    row_count: int,
    status: str,
    attempts: int,
) -> str:
    if status != "success":
        return f"Failed to produce a valid SQL result after {attempts} attempts."

    if isinstance(result_value, list):
        if explanation:
            return f"{explanation.rstrip('.')} Returned {row_count} row(s)."
        return f"Query returned {row_count} row(s)."

    if isinstance(result_value, (int, float)):
        return _summary_from_count(explanation, result_value)

    if explanation:
        return f"{explanation.rstrip('.')} Result: {result_value}."
    return f"Result: {result_value}."


def _summary_from_count(explanation: str | None, value: Any) -> str:
    if not explanation:
        return f"Result: {value}."

    cleaned = explanation.strip()
    lower = cleaned.lower()
    prefixes = [
        "counts the number of ",
        "count the number of ",
        "count of ",
        "counts ",
        "count ",
        "number of ",
    ]
    for prefix in prefixes:
        if lower.startswith(prefix):
            remainder = cleaned[len(prefix):].strip().rstrip(".")
            if remainder:
                return f"There are {value} {remainder}."
            break

    return f"{cleaned.rstrip('.')} Result: {value}."
