"""Generate an evaluation report from SQL_QUESTIONS_filled.xlsx.

This script is intended for manual execution only and is not used by the API server.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any

import openpyxl

from services.pipeline_service import run_pipeline
from services.sql_execution_service import execute_sql
from services.sql_validation_service import validate_sql
from utils.benchmark_compare import compare_result_sets
from utils.benchmark_excel import load_benchmark_cases


def _execute_expected_sql(sql: str) -> tuple[bool, list[dict[str, Any]], str | None]:
    validation = validate_sql(sql)
    if not validation.valid:
        return False, [], validation.reason

    try:
        rows = execute_sql(sql)
        return True, rows, None
    except Exception as exc:
        return False, [], str(exc)


def _bool_to_text(value: bool | None) -> str:
    if value is None:
        return "N/A"
    return "Yes" if value else "No"


def _default_output_path(input_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return input_path.with_name(
        f"{input_path.stem}_report_{timestamp}{input_path.suffix}"
    )


def generate_report(
    input_path: str,
    sheet_name: str | None,
    limit: int | None,
    output_path: str | None,
) -> Path:
    base_dir = Path(__file__).resolve().parent
    cases = load_benchmark_cases(input_path, sheet_name, limit, base_dir)
    if not cases:
        raise ValueError("No rows found to evaluate")

    output = Path(output_path) if output_path else _default_output_path(Path(input_path))

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Evaluation"

    headers = [
        "Question",
        "Generated SQL",
        "Executed successfully",
        "Correct Result",
        "Retry Needed",
        "Final status",
    ]
    sheet.append(headers)

    for idx, case in enumerate(cases, start=1):
        question = case["question"]
        expected_sql = case["expected_sql"]

        print(f"[{idx}/{len(cases)}] {question}")
        ai_result = run_pipeline(question)

        expected_ok, expected_rows, _ = _execute_expected_sql(expected_sql)
        correct_result = None
        if ai_result.status == "success" and expected_ok:
            correct_result = compare_result_sets(ai_result.result, expected_rows)

        row = [
            question,
            ai_result.sql,
            _bool_to_text(ai_result.status == "success"),
            _bool_to_text(correct_result),
            _bool_to_text(ai_result.retried),
            ai_result.status,
        ]
        sheet.append(row)

    workbook.save(output)
    return output


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate an Excel evaluation report for SQL questions."
    )
    parser.add_argument(
        "--input",
        default="SQL_QUESTIONS_filled.xlsx",
        help="Input workbook path (default: SQL_QUESTIONS_filled.xlsx)",
    )
    parser.add_argument(
        "--sheet",
        default=None,
        help="Worksheet name (default: active sheet)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional row limit (default: all rows)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output workbook path (default: auto-generated)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    output = generate_report(
        input_path=args.input,
        sheet_name=args.sheet,
        limit=args.limit,
        output_path=args.output,
    )
    print(f"Report saved to: {output}")


if __name__ == "__main__":
    main()
