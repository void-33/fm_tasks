import argparse
import json
import os
from collections import Counter
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Tuple

import pandas as pd

from database import fetch_schema
from executor import execute_sql
from sql_generator import generate_decomposition, generate_sql, fix_sql


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _make_json_safe(obj: Any) -> Any:
    if isinstance(obj, list):
        return [_make_json_safe(item) for item in obj]
    if isinstance(obj, dict):
        return {key: _make_json_safe(value) for key, value in obj.items()}
    return _json_safe(obj)


def _row_signature(row: Dict[str, Any]) -> str:
    safe_row = _make_json_safe(row)
    return json.dumps(safe_row, sort_keys=True, ensure_ascii=True)


def _results_equal(left: List[Dict[str, Any]], right: List[Dict[str, Any]]) -> bool:
    left_counter = Counter(_row_signature(row) for row in left)
    right_counter = Counter(_row_signature(row) for row in right)
    return left_counter == right_counter


def _generate_sql_for_question(
    question: str,
    schema_text: str,
) -> Tuple[Dict[str, Any], str, bool]:
    decomposition = generate_decomposition(question, schema_text=schema_text)
    sql = generate_sql(question, decomposition, schema_text=schema_text)

    result = execute_sql(sql)
    if result["status"] == "success":
        return decomposition, sql, False

    fixed_sql = fix_sql(
        question,
        decomposition,
        sql,
        result.get("error", ""),
        schema_text=schema_text,
    )
    return decomposition, fixed_sql, True


def evaluate_csv(input_path: str, report_path: str) -> None:
    df = pd.read_csv(input_path)
    if "question" not in df.columns or "sql" not in df.columns:
        raise ValueError("Input CSV must contain 'question' and 'sql' columns.")

    schema_text = fetch_schema()

    generated_sql_list: List[str] = []
    report_rows: List[Dict[str, Any]] = []

    total = len(df)
    for index, row in df.iterrows():
        print(f"Evaluating {index + 1}/{total}...")
        question = str(row.get("question", "")).strip()
        actual_sql = str(row.get("sql", "")).strip()

        if not question or not actual_sql:
            generated_sql_list.append("")
            report_rows.append(
                {
                    "question": question,
                    "generated sql": "",
                    "executed successfully": False,
                    "correct result": False,
                    "retry needed": False,
                    "final status": "failed",
                }
            )
            continue

        decomposition, generated_sql, retry_needed = _generate_sql_for_question(
            question,
            schema_text,
        )
        generated_sql_list.append(generated_sql)

        generated_result = execute_sql(generated_sql)
        actual_result = execute_sql(actual_sql)
        if actual_result.get("status") != "success":
            fixed_actual_sql = fix_sql(
                question,
                decomposition,
                actual_sql,
                actual_result.get("error", ""),
                schema_text=schema_text,
            )
            actual_result = execute_sql(fixed_actual_sql)

        generated_success = generated_result.get("status") == "success"
        actual_success = actual_result.get("status") == "success"

        is_correct = False
        final_status = "failed"

        if actual_success and generated_success:
            is_correct = _results_equal(
                generated_result.get("rows", []),
                actual_result.get("rows", []),
            )
            final_status = "correct" if is_correct else "incorrect"
        elif not actual_success:
            final_status = "reference_failed"

        report_rows.append(
            {
                "question": question,
                "generated sql": generated_sql,
                "executed successfully": generated_success,
                "correct result": is_correct,
                "retry needed": retry_needed,
                "final status": final_status,
            }
        )

    df["generated_sql"] = generated_sql_list
    df.to_csv(input_path, index=False)

    report_df = pd.DataFrame(report_rows)
    report_df.to_csv(report_path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate generated SQL against reference SQL.")
    parser.add_argument(
        "--input",
        default="sql_questions_answers.csv",
        help="Path to the input CSV file.",
    )
    parser.add_argument(
        "--report",
        default="sql_evaluation_report.csv",
        help="Path to the output report CSV file.",
    )

    args = parser.parse_args()
    base_dir = os.path.dirname(os.path.abspath(__file__))
    input_path = args.input
    report_path = args.report

    if not os.path.isabs(input_path):
        input_path = os.path.join(base_dir, input_path)
    if not os.path.isabs(report_path):
        report_path = os.path.join(base_dir, report_path)

    evaluate_csv(input_path, report_path)


if __name__ == "__main__":
    main()
