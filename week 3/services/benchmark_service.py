import asyncio
import time
from pathlib import Path
from typing import Any

import psycopg2

from models import BenchmarkRequest
from services.pipeline_service import run_pipeline
from services.sql_execution_service import execute_sql
from utils.benchmark_compare import compare_result_sets
from utils.benchmark_excel import load_benchmark_cases
from services.sql_validation_service import validate_sql


def _execute_expected_sql(sql: str) -> dict[str, Any]:
    validation = validate_sql(sql)
    if not validation.valid:
        return {
            "sql": sql,
            "row_count": 0,
            "result": [],
            "status": "failed",
            "error": validation.reason,
        }

    try:
        result = execute_sql(sql)
        return {
            "sql": sql,
            "row_count": len(result),
            "result": result,
            "status": "success",
            "error": None,
        }
    except (psycopg2.Error, Exception) as exec_err:
        return {
            "sql": sql,
            "row_count": 0,
            "result": [],
            "status": "failed",
            "error": str(exec_err),
        }


async def _run_benchmark_case(case: dict[str, Any], semaphore: asyncio.Semaphore) -> dict[str, Any]:
    async with semaphore:
        ai_task = asyncio.to_thread(run_pipeline, case["question"])
        actual_task = asyncio.to_thread(_execute_expected_sql, case["expected_sql"])
        ai_result, actual_result = await asyncio.gather(ai_task, actual_task)

    result_match = None
    if ai_result.status == "success" and actual_result["status"] == "success":
        result_match = compare_result_sets(ai_result.result, actual_result["result"])

    return {
        "row": case["row"],
        "question": case["question"],
        "expected": case["expected"],
        "expected_sql": case["expected_sql"],
        "ai": ai_result.model_dump(),
        "actual": actual_result,
        "comparison": {
            "result_match": result_match,
        },
    }


async def run_benchmark(req: BenchmarkRequest) -> dict[str, Any]:
    if req.limit is not None and req.limit <= 0:
        raise ValueError("limit must be a positive integer")
    if req.max_concurrency <= 0:
        raise ValueError("max_concurrency must be positive")

    base_dir = Path(__file__).resolve().parent.parent
    cases = load_benchmark_cases(req.file_path, req.sheet_name, req.limit, base_dir)
    if not cases:
        raise ValueError("No benchmark rows found to evaluate")

    started = time.time()
    semaphore = asyncio.Semaphore(min(req.max_concurrency, len(cases)))
    tasks = [_run_benchmark_case(case, semaphore) for case in cases]
    results = await asyncio.gather(*tasks)

    total = len(results)
    ai_success = sum(1 for r in results if r["ai"]["status"] == "success")
    ai_failed = total - ai_success
    actual_success = sum(1 for r in results if r["actual"]["status"] == "success")
    actual_failed = total - actual_success

    retried = sum(1 for r in results if r["ai"]["retried"])
    retry_fixed = sum(1 for r in results if r["ai"]["retry_fixed"])

    match_count = sum(1 for r in results if r["comparison"]["result_match"] is True)
    match_evaluated = sum(
        1 for r in results if r["comparison"]["result_match"] is not None
    )

    latencies = [
        r["ai"]["latency_ms"]
        for r in results
        if r["ai"]["latency_ms"] is not None
    ]
    avg_latency = int(sum(latencies) / len(latencies)) if latencies else 0
    benchmark_latency = int((time.time() - started) * 1000)

    return {
        "summary": {
            "total_questions": total,
            "ai_success_count": ai_success,
            "ai_failed_count": ai_failed,
            "sql_execution_success_rate_pct": round(ai_success / total * 100, 1)
            if total
            else 0,
            "actual_success_count": actual_success,
            "actual_failed_count": actual_failed,
            "correct_sql_result_count": match_count,
            "correct_sql_result_rate_pct": round(match_count / match_evaluated * 100, 1)
            if match_evaluated
            else 0,
            "retried_count": retried,
            "retry_fixed_count": retry_fixed,
            "retry_success_rate_pct": round(retry_fixed / retried * 100, 1)
            if retried
            else 0,
            "avg_generation_latency_ms": avg_latency,
            "benchmark_latency_ms": benchmark_latency,
        },
        "results": results,
    }
