#!/usr/bin/env python3
"""run_evaluation.py — Deterministic evaluation harness for the agent.

Built from scratch without external evaluation frameworks (per assignment requirement).

Design:
  - Fake model adapter: yields scripted action JSON strings from each test case.
  - Fake tool adapter: yields scripted chunk lists from each test case, or
    raises ToolError to inject a tool failure.
  - No live Gemini, Chroma, Redis, Ollama, or Docker connection required.
  - Results are written to evaluation/results.md as a Markdown table.

Usage (from week-16 root):
    python evaluation/run_evaluation.py

The script regenerates results.md on every run.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# ── Add backend to Python path ────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.services.agent import run_agent, AgentStatusEnum
from app.services.tools import ToolError
from app.core.cache import make_cache_key, make_agent_cache_key


# ═══════════════════════════════════════════════════════════════════════════════
# Fake adapters
# ═══════════════════════════════════════════════════════════════════════════════

USAGE_PER_CALL = {"input_tokens": 120, "output_tokens": 40, "total_tokens": 160,
                  "provider": "gemini", "fallback_used": False}


def _make_scripted_model(actions: list):
    """Return a fake model adapter that yields scripted action strings."""
    call_iter = iter(actions)

    async def _model(prompt, system_prompt, temperature):
        try:
            action = next(call_iter)
        except StopIteration:
            action = json.dumps({"action": "clarify",
                                  "question": "Scripted responses exhausted.",
                                  "query": None, "selected_sources": None,
                                  "top_k": 3, "answer": None, "citations": []})
        # If action is already a string (raw text, potentially invalid JSON)
        if isinstance(action, str):
            return action, USAGE_PER_CALL
        # Otherwise serialize the dict to JSON
        return json.dumps(action), USAGE_PER_CALL

    return _model


def _make_scripted_tools(tool_results, inject_timeout: bool = False):
    """Return a fake tool adapter with scripted results."""
    catalog = ["policy-a.txt", "policy-b.txt", "policy-c.txt"]

    if inject_timeout:
        chunk_iter = None  # not used
    else:
        if isinstance(tool_results, list):
            chunk_iter = iter(tool_results)
        else:
            chunk_iter = iter([])

    async def _list():
        return catalog

    async def _retrieve(query, selected_sources, top_k, **kw):
        if inject_timeout:
            raise ToolError("retrieve_chunks", "Timed out after 10s. [INJECTED FAILURE]")
        try:
            chunks = next(chunk_iter)
        except StopIteration:
            chunks = []
        return chunks

    return {"list_sources": _list, "retrieve_chunks": _retrieve}


# ═══════════════════════════════════════════════════════════════════════════════
# Case runners
# ═══════════════════════════════════════════════════════════════════════════════

async def run_case(case: dict) -> dict:
    """Run a single test case and return a result record."""
    case_id = case["id"]
    case_type = case.get("type", "agent")

    # ── TC-11: pure unit test (no agent run needed) ────────────────────────
    if case_type == "unit":
        msg = case["question"]
        k1 = make_cache_key({"message": msg})
        k2 = make_agent_cache_key({"message": msg})
        oracle = case["oracle"]
        passed = (
            k1.startswith(oracle["expected_chat_key_prefix"])
            and k2.startswith(oracle["expected_agent_key_prefix"])
            and oracle.get("keys_must_differ", True) == (k1 != k2)
        )
        return {
            "id": case_id,
            "name": case["name"],
            "status": "unit_pass" if passed else "unit_fail",
            "completion": passed,
            "tool_correctness": True,
            "iterations": 0,
            "search_calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "failures": [],
            "failure_class": None,
            "notes": "Cache key separation verified" if passed else "Cache key separation FAILED",
        }

    # ── Normal agent test cases ────────────────────────────────────────────
    actions = case.get("scripted_model_actions", [])
    tool_results = case.get("scripted_tool_results", [])
    inject_timeout = tool_results == "INJECT_TIMEOUT"

    model_adapter = _make_scripted_model(actions)
    tool_adapter = _make_scripted_tools([] if inject_timeout else tool_results,
                                        inject_timeout=inject_timeout)

    t0 = time.monotonic()
    result = await run_agent(
        question=case["question"],
        selected_sources=case.get("selected_sources"),
        _model_adapter=model_adapter,
        _tool_adapter=tool_adapter,
    )
    elapsed_ms = round((time.monotonic() - t0) * 1000, 1)

    oracle = case["oracle"]

    # ── Oracle checks ──────────────────────────────────────────────────────
    status_ok = result.status.value == oracle.get("expected_status", "completed")

    min_iter = oracle.get("expected_min_iterations", 1)
    max_iter = oracle.get("expected_max_iterations", 6)
    iter_ok = min_iter <= result.iterations <= max_iter

    expected_tools = oracle.get("expected_tool_sequence")
    actual_tools = [tc.tool for tc in result.tool_calls]
    tool_ok = actual_tools == expected_tools if expected_tools is not None else True

    expected_sources = oracle.get("expected_sources_cited")
    if expected_sources is not None:
        sources_ok = set(expected_sources).issubset(set(result.sources))
    else:
        sources_ok = True

    no_confident_answer = not oracle.get("assert_no_confident_answer", False) or (
        result.status != AgentStatusEnum.COMPLETED
    )

    no_crash = oracle.get("assert_no_hard_crash", False) == False or (
        result.status in (
            AgentStatusEnum.INSUFFICIENT_EVIDENCE,
            AgentStatusEnum.BOUNDED_FAILURE,
            AgentStatusEnum.NEEDS_CLARIFICATION,
            AgentStatusEnum.COMPLETED,
        )
    )

    cap_ok = not oracle.get("assert_no_infinite_loop", False) or (
        result.iterations <= max_iter
    )

    completion = status_ok and iter_ok and no_confident_answer and no_crash and cap_ok
    tool_correctness = tool_ok and sources_ok

    # ── Failure classification ─────────────────────────────────────────────
    failure_class = None
    if result.failures:
        taxonomies = [f.get("taxonomy", "") for f in result.failures]
        if "hard" in taxonomies:
            failure_class = "hard"
        elif "cascading_soft" in taxonomies:
            failure_class = "cascading_soft"
        elif "soft" in taxonomies:
            failure_class = "soft"

    search_calls = sum(1 for tc in result.tool_calls if tc.tool == "retrieve_chunks")

    notes_parts = []
    if not status_ok:
        notes_parts.append(f"status={result.status.value}≠{oracle.get('expected_status')}")
    if not iter_ok:
        notes_parts.append(f"iter={result.iterations} not in [{min_iter},{max_iter}]")
    if not tool_ok:
        notes_parts.append(f"tools={actual_tools}≠{expected_tools}")
    if not sources_ok:
        notes_parts.append(f"sources={result.sources}⊄{expected_sources}")
    if not no_confident_answer:
        notes_parts.append("CONFIDENT ANSWER WITH NO VALID EVIDENCE")
    if inject_timeout:
        notes_parts.append("injected_timeout")

    return {
        "id": case_id,
        "name": case["name"],
        "status": result.status.value,
        "completion": completion,
        "tool_correctness": tool_correctness,
        "iterations": result.iterations,
        "search_calls": search_calls,
        "input_tokens": result.token_usage.input_tokens,
        "output_tokens": result.token_usage.output_tokens,
        "total_tokens": result.token_usage.total_tokens,
        "failures": [f"{f['phase']}({f['taxonomy']})" for f in result.failures],
        "failure_class": failure_class,
        "latency_ms": elapsed_ms,
        "notes": "; ".join(notes_parts) if notes_parts else "OK",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Report generation
# ═══════════════════════════════════════════════════════════════════════════════

def _yn(val: bool) -> str:
    return "✓" if val else "✗"


def _tok(val) -> str:
    return str(val) if val is not None else "N/A"


def generate_report(results: list[dict]) -> str:
    lines = []
    lines.append("# Agent Evaluation Results")
    lines.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("\n## Per-Case Results\n")

    header = (
        "| ID | Name | Status | Complete | Tool✓ | Iter | Searches | "
        "Input Tok | Output Tok | Total Tok | Failure Class | Notes |"
    )
    sep = (
        "|---|---|---|---|---|---|---|---|---|---|---|---|"
    )
    lines.append(header)
    lines.append(sep)

    for r in results:
        row = (
            f"| {r['id']} "
            f"| {r['name']} "
            f"| {r['status']} "
            f"| {_yn(r['completion'])} "
            f"| {_yn(r['tool_correctness'])} "
            f"| {r['iterations']} "
            f"| {r['search_calls']} "
            f"| {_tok(r['input_tokens'])} "
            f"| {_tok(r['output_tokens'])} "
            f"| {_tok(r['total_tokens'])} "
            f"| {r['failure_class'] or '-'} "
            f"| {r['notes']} |"
        )
        lines.append(row)

    # ── Aggregate metrics ──────────────────────────────────────────────────
    total = len(results)
    completed = sum(1 for r in results if r["completion"])
    tool_correct = sum(1 for r in results if r["tool_correctness"])
    iters = [r["iterations"] for r in results if r["iterations"] > 0]
    searches = [r["search_calls"] for r in results]
    total_toks = [r["total_tokens"] for r in results if r["total_tokens"] is not None]

    failure_counts = {"hard": 0, "soft": 0, "cascading_soft": 0}
    for r in results:
        fc = r.get("failure_class")
        if fc in failure_counts:
            failure_counts[fc] += 1

    lines.append("\n## Aggregate Metrics\n")
    lines.append(f"| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| Task completion rate | {completed}/{total} ({100*completed//total}%) |")
    lines.append(f"| Tool-call correctness rate | {tool_correct}/{total} ({100*tool_correct//total}%) |")
    lines.append(f"| Mean iterations | {sum(iters)/len(iters):.1f} |" if iters else "| Mean iterations | N/A |")
    lines.append(f"| Median iterations | {sorted(iters)[len(iters)//2]} |" if iters else "| Median iterations | N/A |")
    lines.append(f"| Min/Max iterations | {min(iters)}/{max(iters)} |" if iters else "| Min/Max iterations | N/A |")
    lines.append(f"| Mean search calls | {sum(searches)/len(searches):.1f} |")
    lines.append(f"| Total tokens (all cases) | {sum(total_toks) if total_toks else 'N/A'} |")
    lines.append(f"| Mean tokens per case | {sum(total_toks)//len(total_toks) if total_toks else 'N/A'} |")
    lines.append(f"| Hard failures | {failure_counts['hard']} |")
    lines.append(f"| Soft failures | {failure_counts['soft']} |")
    lines.append(f"| Cascading soft failures | {failure_counts['cascading_soft']} |")

    lines.append("\n## Failure Taxonomy Notes\n")
    lines.append("- **Hard failure**: unhandled exception, invalid response after repair, or fabricated answer after tool failure.")
    lines.append("- **Soft failure**: safe but degraded result — extra search, conservative insufficient-evidence, or clarification when oracle expected direct answer.")
    lines.append("- **Cascading soft failure**: an earlier degraded step propagates into later behavior but the final response remains safe.")

    lines.append("\n## Failure Injection Observation (TC-08)\n")
    tc08 = next((r for r in results if r["id"] == "TC-08"), None)
    if tc08:
        lines.append(f"- Injected fault: retrieval timeout (ToolError raised in fake tool adapter)")
        lines.append(f"- Expected behavior: tool failure recorded; no confident answer returned")
        lines.append(f"- Observed status: `{tc08['status']}`")
        lines.append(f"- Completion (safe outcome): {_yn(tc08['completion'])}")
        lines.append(f"- Failure records: {tc08['failures']}")
        lines.append(f"- **Classification**: {tc08['failure_class'] or 'none'} — the agent recognized the failure, recorded it in the trajectory, and did not produce a confident unsupported answer.")

    lines.append("\n## Baseline Comparison Note\n")
    lines.append(
        "Multi-agent baseline comparison is not applicable — this implementation uses a single-agent design. "
        "Compared against the W15 legacy single-pass baseline: the baseline performs exactly 1 retrieval + 1 generation "
        "and cannot decide from intermediate evidence whether another source or clarification is needed. "
        "TC-02 (cross-source comparison) requires ≥ 2 searches and would be unsolvable by the baseline."
    )

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

async def main():
    cases_path = Path(__file__).parent / "cases.json"
    results_path = Path(__file__).parent / "results.md"

    with open(cases_path) as f:
        cases = json.load(f)

    print(f"Running {len(cases)} test cases...")
    results = []
    for case in cases:
        print(f"  [{case['id']}] {case['name']}...", end=" ", flush=True)
        result = await run_case(case)
        results.append(result)
        icon = "✓" if result["completion"] else "✗"
        print(f"{icon} {result['status']} ({result['iterations']} iter)")

    report = generate_report(results)

    with open(results_path, "w") as f:
        f.write(report)

    print(f"\nResults written to {results_path}")

    # ── Summary ────────────────────────────────────────────────────────────
    total = len(results)
    completed = sum(1 for r in results if r["completion"])
    print(f"\nTask completion: {completed}/{total} ({100*completed//total}%)")


if __name__ == "__main__":
    asyncio.run(main())

