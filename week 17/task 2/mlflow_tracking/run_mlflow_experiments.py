#!/usr/bin/env python3
"""
run_mlflow_experiments.py — Run agent evaluation for each prompt version
and log everything to MLflow.

No live LLM calls. Uses scripted adapters from evaluation/run_evaluation.py.
Run: uv run python mlflow_tracking/run_mlflow_experiments.py
"""
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "evaluation"))

import mlflow
from run_evaluation import run_case  # import the existing case runner

CASES_PATH = ROOT / "evaluation" / "cases.json"
PROMPTS_DIR = ROOT / "prompts"
MLRUNS_DIR = ROOT / "mlruns"

PROMPT_VERSIONS = ["v1", "v2", "v3"]

PROMPT_CONFIGS = {
    "v1": {
        "prompt_version": "v1",
        "model": "gemini-2.0-flash",
        "temperature": 0.2,
        "agent_max_steps": 6,
        "agent_max_searches": 4,
        "change_description": "Baseline — exact W16 production system prompt",
    },
    "v2": {
        "prompt_version": "v2",
        "model": "gemini-2.0-flash",
        "temperature": 0.2,
        "agent_max_steps": 6,
        "agent_max_searches": 4,
        "change_description": "Added step budget guidance and multi-source search instructions",
    },
    "v3": {
        "prompt_version": "v3",
        "model": "gemini-2.0-flash",
        "temperature": 0.2,
        "agent_max_steps": 6,
        "agent_max_searches": 4,
        "change_description": "Added empty-result handling: require >= 2 empty searches before clarifying",
    },
}


async def evaluate_all_cases(cases: list, version: str) -> dict:
    results = []
    traces = []

    for case in cases:
        result = await run_case(case)
        results.append(result)

        if case.get("type") != "unit":
            trace = {
                "prompt_version": version,
                "case_id": case["id"],
                "query": case["question"],
                "status": result["status"],
                "completion": result["completion"],
                "iterations": result["iterations"],
                "search_calls": result["search_calls"],
                "token_usage": {
                    "input": result.get("input_tokens"),
                    "output": result.get("output_tokens"),
                    "total": result.get("total_tokens"),
                },
                "failures": result["failures"],
                "notes": result["notes"],
            }
            traces.append(trace)

    total = len(results)
    completed = sum(1 for r in results if r["completion"])
    tool_correct = sum(1 for r in results if r["tool_correctness"])
    iters = [r["iterations"] for r in results if r["iterations"] > 0]
    toks = [r["total_tokens"] for r in results if r.get("total_tokens") is not None]

    return {
        "results": results,
        "traces": traces,
        "metrics": {
            "pct_tests_passed": completed / total if total > 0 else 0.0,
            "task_completion_rate": completed / total if total > 0 else 0.0,
            "tool_correctness_rate": tool_correct / total if total > 0 else 0.0,
            "mean_iterations": sum(iters) / len(iters) if iters else 0.0,
            "mean_tokens": sum(toks) / len(toks) if toks else 0.0,
            "total_cases": float(total),
            "completed_cases": float(completed),
        },
    }


def main():
    mlflow.set_tracking_uri(str(MLRUNS_DIR))
    mlflow.set_experiment("agent_prompt_experiments")

    with open(CASES_PATH) as f:
        cases = json.load(f)

    for version in PROMPT_VERSIONS:
        config = PROMPT_CONFIGS[version]
        prompt_path = PROMPTS_DIR / f"prompt_{version}.txt"

        print(f"\n{'='*60}")
        print(f"Running experiment: prompt_{version}")
        print(f"Description: {config['change_description']}")

        with mlflow.start_run(run_name=f"prompt_{version}"):
            mlflow.log_params(config)

            eval_result = asyncio.run(evaluate_all_cases(cases, version))
            mlflow.log_metrics(eval_result["metrics"])
            print(f"Metrics: {eval_result['metrics']}")

            if prompt_path.exists():
                mlflow.log_artifact(str(prompt_path), artifact_path="prompts")

            with tempfile.TemporaryDirectory() as tmpdir:
                all_traces_path = os.path.join(tmpdir, f"traces_{version}.json")
                with open(all_traces_path, "w") as f:
                    json.dump(eval_result["traces"], f, indent=2)
                mlflow.log_artifact(all_traces_path, artifact_path="traces")

                success = next(
                    (t for t in eval_result["traces"] if t["completion"]), None
                )
                if success:
                    p = os.path.join(tmpdir, f"trace_success_{version}.json")
                    with open(p, "w") as f:
                        json.dump(success, f, indent=2)
                    mlflow.log_artifact(p, artifact_path="traces")

                failure = next(
                    (t for t in eval_result["traces"] if not t["completion"]), None
                )
                if failure:
                    p = os.path.join(tmpdir, f"trace_failure_{version}.json")
                    with open(p, "w") as f:
                        json.dump(failure, f, indent=2)
                    mlflow.log_artifact(p, artifact_path="traces")

            print("Run logged to MLflow.")

    print("\nAll experiments done.")
    print(f"MLflow UI: uv run mlflow ui --backend-store-uri {MLRUNS_DIR}")


if __name__ == "__main__":
    main()
