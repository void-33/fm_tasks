#!/usr/bin/env python3
"""run_tests.py — Standalone test runner for backend unit tests.

Executes test suites in backend/tests/ without requiring pytest binary or external services.
Can be executed with:
    python backend/tests/run_tests.py
"""

import asyncio
import sys
from pathlib import Path

# Add backend directory to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.test_agent import (
    TestActionValidation,
    TestTwoIterationLoop,
    TestMaxStepsCap,
    TestNoProgressDetection,
    TestClarificationTerminal,
    TestToolFailure,
    TestMalformedAction,
    TestCacheKeySeparation,
    TestTokenAggregation,
    TestFinalWithoutEvidence,
)


async def main():
    print("=== Running Backend Agent Unit Tests ===")

    # 1. Action validation
    print("\n[1/10] Testing Action Validation...")
    v = TestActionValidation()
    v.test_valid_search()
    v.test_valid_clarify()
    v.test_valid_final()
    v.test_search_requires_query()
    v.test_search_cannot_have_answer()
    v.test_clarify_requires_question()
    v.test_clarify_cannot_have_answer()
    v.test_final_requires_answer()
    v.test_final_cannot_have_query()
    print("  ✓ Action validation passed")

    # 2. Two iteration loop
    print("\n[2/10] Testing Two Iteration Loop (Cross-source)...")
    loop_test = TestTwoIterationLoop()
    await loop_test.test_two_searches_then_final()
    print("  ✓ Two-iteration loop passed (iterations >= 2)")

    # 3. Max steps cap
    print("\n[3/10] Testing Max Steps Cap...")
    cap_test = TestMaxStepsCap()
    await cap_test.test_loop_stops_at_max_steps()
    await cap_test.test_client_cannot_exceed_server_max()
    print("  ✓ Max-steps cap passed")

    # 4. No progress detection
    print("\n[4/10] Testing No-Progress Detection...")
    np_test = TestNoProgressDetection()
    await np_test.test_repeated_identical_search_stops_loop()
    print("  ✓ No-progress detection passed")

    # 5. Clarification terminal
    print("\n[5/10] Testing Clarification Terminal...")
    clar_test = TestClarificationTerminal()
    await clar_test.test_clarify_stops_with_no_answer()
    print("  ✓ Clarification terminal passed")

    # 6. Tool failure
    print("\n[6/10] Testing Tool Failure Injection...")
    tf_test = TestToolFailure()
    await tf_test.test_tool_timeout_recorded_no_confident_answer()
    print("  ✓ Tool failure handling passed")

    # 7. Malformed action repair
    print("\n[7/10] Testing Malformed Action JSON & Repair...")
    ma_test = TestMalformedAction()
    await ma_test.test_malformed_json_triggers_repair_then_bounded_failure()
    print("  ✓ Malformed action handling passed")

    # 8. Cache key separation
    print("\n[8/10] Testing Cache Key Separation (chat: vs agent:)...")
    ck_test = TestCacheKeySeparation()
    ck_test.test_same_message_different_keys_for_chat_vs_agent()
    ck_test.test_agent_keys_are_deterministic()
    print("  ✓ Cache key separation passed")

    # 9. Token aggregation
    print("\n[9/10] Testing Token Aggregation...")
    ta_test = TestTokenAggregation()
    await ta_test.test_tokens_accumulated_across_iterations()
    print("  ✓ Token aggregation passed")

    # 10. Final without evidence
    print("\n[10/10] Testing Final Answer Without Citations...")
    fe_test = TestFinalWithoutEvidence()
    await fe_test.test_final_with_no_ledger_becomes_insufficient_evidence()
    print("  ✓ Insufficient evidence conversion passed")

    print("\n" + "=" * 45)
    print("ALL 10 UNIT TEST SUITES PASSED (100%)")
    print("=" * 45)


if __name__ == "__main__":
    asyncio.run(main())

