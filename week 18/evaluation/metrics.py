"""
Evaluation metrics for the Healthcare Q&A Guardrail System.

Computes precision, recall, F1, false positives, and false negatives
across a test suite.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class TestResult:
    """
    Stores the result of a single test case.

    Fields
    ------
    test_id : str
        Unique identifier (e.g. "TC-01").
    description : str
        Human-readable description of what is being tested.
    input_text : str
        The raw user input fed to the guardrail system.
    reference_context : str
        Reference document provided alongside the input (for groundedness tests).
    raw_output : Any
        The simulated AI output (dict) fed to the output guardrails.
    expected_behavior : str
        What the guardrail system *should* do (free text).
    expected_flag : bool
        True if the guardrail is expected to fire (detect / block / flag).
    actual_flag : bool
        True if the guardrail actually fired.
    actual_behavior : str
        Observed system behaviour (free text).
    passed : bool
        Whether actual_flag == expected_flag.
    guardrail_tested : str
        Which guardrail this test targets.
    """
    test_id: str
    description: str
    input_text: str
    reference_context: str
    raw_output: Any
    expected_behavior: str
    expected_flag: bool
    actual_flag: bool
    actual_behavior: str
    passed: bool
    guardrail_tested: str


@dataclass
class GuardrailMetrics:
    """Precision, recall, and related metrics for a set of test results."""
    guardrail: str
    total: int
    passed: int
    failed: int
    true_positives: int
    true_negatives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float
    accuracy: float


def compute_metrics(results: list[TestResult]) -> dict[str, GuardrailMetrics]:
    """
    Compute per-guardrail metrics from a list of TestResult objects.

    Returns a dict mapping guardrail name → GuardrailMetrics.
    """
    guardrails: dict[str, list[TestResult]] = {}
    for r in results:
        guardrails.setdefault(r.guardrail_tested, []).append(r)

    metrics: dict[str, GuardrailMetrics] = {}

    for name, cases in guardrails.items():
        tp = sum(1 for c in cases if c.expected_flag and c.actual_flag)
        tn = sum(1 for c in cases if not c.expected_flag and not c.actual_flag)
        fp = sum(1 for c in cases if not c.expected_flag and c.actual_flag)
        fn = sum(1 for c in cases if c.expected_flag and not c.actual_flag)

        total = len(cases)
        passed = sum(1 for c in cases if c.passed)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )
        accuracy = (tp + tn) / total if total > 0 else 0.0

        metrics[name] = GuardrailMetrics(
            guardrail=name,
            total=total,
            passed=passed,
            failed=total - passed,
            true_positives=tp,
            true_negatives=tn,
            false_positives=fp,
            false_negatives=fn,
            precision=round(precision, 3),
            recall=round(recall, 3),
            f1=round(f1, 3),
            accuracy=round(accuracy, 3),
        )

    return metrics


def print_metrics_table(metrics: dict[str, GuardrailMetrics]) -> None:
    """Pretty-print metrics to stdout."""
    header = f"{'Guardrail':<30} {'Total':>6} {'Pass':>6} {'Fail':>6} {'TP':>4} {'TN':>4} {'FP':>4} {'FN':>4} {'Prec':>6} {'Rec':>6} {'F1':>6} {'Acc':>6}"
    print("\n" + "=" * len(header))
    print("GUARDRAIL EVALUATION METRICS")
    print("=" * len(header))
    print(header)
    print("-" * len(header))
    for m in metrics.values():
        print(
            f"{m.guardrail:<30} {m.total:>6} {m.passed:>6} {m.failed:>6} "
            f"{m.true_positives:>4} {m.true_negatives:>4} {m.false_positives:>4} {m.false_negatives:>4} "
            f"{m.precision:>6.3f} {m.recall:>6.3f} {m.f1:>6.3f} {m.accuracy:>6.3f}"
        )
    print("=" * len(header) + "\n")
