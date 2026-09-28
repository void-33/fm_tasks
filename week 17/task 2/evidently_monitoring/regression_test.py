#!/usr/bin/env python3
"""
regression_test.py — Evidently AI regression testing for each prompt version.

Compares new prompt responses against golden reference responses.
Uses word-overlap scoring as a proxy for semantic similarity.
Threshold: 60% of tests must pass to promote a prompt version.

Run: uv run python evidently_monitoring/regression_test.py
"""
import os
from pathlib import Path

import mlflow
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
MLRUNS_DIR = ROOT / "mlruns"
REPORTS_DIR = ROOT / "reports"

GOLDEN_REFERENCE_SET = [
    {
        "query": "What is the return window in policy A?",
        "golden_response": "Policy A allows returns within 30 days of purchase.",
        "category": "factual_lookup",
    },
    {
        "query": "Compare refund policies in policy-a.txt and policy-b.txt.",
        "golden_response": (
            "Policy A allows returns within 30 days. Policy B accepts refunds within 14 days. "
            "Policy A offers a longer return window."
        ),
        "category": "cross_source_comparison",
    },
    {
        "query": "What is the refund period?",
        "golden_response": (
            "Sources conflict: policy-a.txt states 30 days while policy-c.txt states 60 days. "
            "The applicable period depends on which policy governs your situation."
        ),
        "category": "conflict_detection",
    },
    {
        "query": "Can I get my money back?",
        "golden_response": "Yes, you can get a refund within 30 days of purchase according to Policy A.",
        "category": "informal_rephrasing",
    },
    {
        "query": "What is the warranty period for product X?",
        "golden_response": (
            "I could not find warranty information in the uploaded documents. "
            "Please upload a warranty document or contact support."
        ),
        "category": "no_evidence",
    },
]

SIMULATED_RESPONSES = {
    "v1": [
        "Policy A allows returns within 30 days.",
        "Policy A: 30 days. Policy B: 14 days.",
        "Sources conflict: policy-a.txt says 30 days; policy-c.txt says 60 days. Please verify with the relevant department.",
        "Yes, you can get a refund within 30 days.",
        "I could not find warranty information in the uploaded documents. Could you upload a warranty document or rephrase your question?",
    ],
    "v2": [
        "Policy A allows returns within 30 days of purchase.",
        "Policy A accepts refunds within 30 days. Policy B accepts refunds within 14 days. Policy A has the longer return window.",
        "There is a conflict between sources: policy-a.txt states 30 days and policy-c.txt states 60 days.",
        "Yes, according to Policy A, refunds are accepted within 30 days of purchase.",
        "I searched the available documents but could not find warranty information for product X. Please upload a warranty document.",
    ],
    "v3": [
        "Policy A allows returns within 30 days.",
        "After searching both documents: Policy A offers a 30-day return window, while Policy B offers 14 days.",
        "The evidence shows conflicting information: policy-a.txt says 30 days, policy-c.txt says 60 days. Please clarify which policy applies.",
        "Yes, you can get a refund. Policy A accepts returns within 30 days of purchase.",
        "No warranty information was found in the uploaded documents. I tried multiple search terms. Please upload the relevant warranty document.",
    ],
}

PROMOTION_THRESHOLD = 0.60


def score_response(reference: str, response: str, threshold: float = 0.40) -> dict:
    """
    Score a response against a reference answer.
    Uses word-overlap ratio as a proxy for semantic similarity.
    """
    ref_words = set(reference.lower().split())
    resp_words = set(response.lower().split())
    if not ref_words:
        return {"passed": True, "score": 1.0, "method": "empty_reference"}
    overlap = len(ref_words & resp_words) / len(ref_words)
    return {
        "passed": overlap >= threshold,
        "score": overlap,
        "method": "word_overlap",
    }


def generate_html_report(version: str, queries, golden, responses, scores) -> str:
    rows = ""
    for i in range(len(queries)):
        color = "green" if scores[i]["passed"] else "red"
        rows += f"""
        <tr>
          <td>{queries[i]}</td>
          <td style='color:gray'>{golden[i]}</td>
          <td style='color:{color}'>{responses[i]}</td>
          <td>{'✓' if scores[i]['passed'] else '✗'}</td>
          <td>{scores[i]['score']:.2f}</td>
        </tr>"""

    n_passed = sum(1 for s in scores if s["passed"])
    pct = n_passed / len(scores) if scores else 0
    status = "PASS ✓" if pct >= PROMOTION_THRESHOLD else "FAIL ✗"

    return f"""<!DOCTYPE html>
<html>
<head><title>Regression Test — Prompt {version}</title></head>
<body>
<h1>Regression Test Results — Prompt {version}</h1>
<p><strong>Overall:</strong> {n_passed}/{len(scores)} passed ({pct:.1%}) — {status}</p>
<p><strong>Promotion threshold:</strong> {PROMOTION_THRESHOLD:.0%}</p>
<table border="1" cellpadding="6" style="border-collapse:collapse; width:100%">
  <thead>
    <tr>
      <th>Query</th><th>Golden Reference</th><th>New Response</th>
      <th>Pass</th><th>Overlap Score</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>
<p><em>Scoring method: word overlap ratio (threshold {0.40}). 
For LLM-as-judge, set GEMINI_API_KEY and use evidently[llm] BinaryClassificationPromptTemplate.</em></p>
</body></html>"""


def run_regression_test_for_version(version: str) -> dict:
    os.makedirs(str(REPORTS_DIR), exist_ok=True)

    queries = [item["query"] for item in GOLDEN_REFERENCE_SET]
    golden = [item["golden_response"] for item in GOLDEN_REFERENCE_SET]
    responses = SIMULATED_RESPONSES[version]

    scores = [score_response(g, r) for g, r in zip(golden, responses)]
    n_passed = sum(1 for s in scores if s["passed"])
    pct_passed = n_passed / len(scores) if scores else 0

    html = generate_html_report(version, queries, golden, responses, scores)
    report_path = str(REPORTS_DIR / f"regression_test_{version}.html")
    with open(report_path, "w") as f:
        f.write(html)

    try:
        from evidently.report import Report
        from evidently.metrics import TextLengthMetric

        ref_df = pd.DataFrame({"answer": golden})
        cur_df = pd.DataFrame({"answer": responses})

        evidently_report = Report(metrics=[TextLengthMetric(column_name="answer")])
        evidently_report.run(reference_data=ref_df, current_data=cur_df)
        evidently_path = str(REPORTS_DIR / f"evidently_regression_{version}.html")
        evidently_report.save_html(evidently_path)
        print(f"  Evidently report saved: {evidently_path}")
    except Exception as e:
        print(f"  Evidently LLM metrics skipped: {e}")

    print(f"  Version {version}: {n_passed}/{len(scores)} passed ({pct_passed:.1%})")
    print(f"  Report: {report_path}")

    return {
        "version": version,
        "n_passed": n_passed,
        "n_total": len(scores),
        "pct_tests_passed": pct_passed,
        "report_path": report_path,
        "scores": scores,
        "promoted": pct_passed >= PROMOTION_THRESHOLD,
    }


def main():
    mlflow.set_tracking_uri(str(MLRUNS_DIR))
    mlflow.set_experiment("agent_prompt_experiments")

    print("Running regression tests for all prompt versions...")

    for version in ["v1", "v2", "v3"]:
        print(f"\nPrompt {version}:")

        result = run_regression_test_for_version(version)

        with mlflow.start_run(run_name=f"regression_test_{version}"):
            mlflow.log_params({
                "prompt_version": version,
                "test_type": "regression",
                "n_golden_cases": result["n_total"],
                "promotion_threshold": PROMOTION_THRESHOLD,
            })
            mlflow.log_metrics({
                "pct_tests_passed": result["pct_tests_passed"],
                "n_passed": float(result["n_passed"]),
            })
            mlflow.log_artifact(result["report_path"], artifact_path="regression_reports")

        status = "✓ PROMOTED" if result["promoted"] else "✗ NOT PROMOTED"
        print(f"  {status} (threshold: {PROMOTION_THRESHOLD:.0%})")

    print("\nRegression testing complete.")
    print(f"Reports: {REPORTS_DIR}/")
    print(f"MLflow UI: uv run mlflow ui --backend-store-uri {MLRUNS_DIR}")


if __name__ == "__main__":
    main()
