# Agent Evaluation Results

Generated: 2026-09-19 19:16:23

## Per-Case Results

| ID | Name | Status | Complete | Tool✓ | Iter | Searches | Input Tok | Output Tok | Total Tok | Failure Class | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| TC-01 | Single-source factual query | completed | ✓ | ✓ | 2 | 1 | 240 | 80 | 320 | - | OK |
| TC-02 | Cross-source comparison | completed | ✓ | ✓ | 3 | 2 | 360 | 120 | 480 | - | OK |
| TC-03 | Conflicting evidence | completed | ✓ | ✓ | 3 | 2 | 360 | 120 | 480 | - | OK |
| TC-04 | Ambiguous request — clarification | needs_clarification | ✓ | ✓ | 1 | 0 | 120 | 40 | 160 | - | OK |
| TC-05 | No relevant evidence | needs_clarification | ✓ | ✓ | 2 | 1 | 240 | 80 | 320 | - | OK |
| TC-06 | Revised query — better search term | completed | ✓ | ✓ | 3 | 2 | 360 | 120 | 480 | - | OK |
| TC-07 | Invalid action JSON — repair | bounded_failure | ✓ | ✓ | 1 | 0 | 240 | 80 | 320 | hard | OK |
| TC-08 | Tool unavailable — injected timeout | insufficient_evidence | ✓ | ✓ | 2 | 1 | 240 | 80 | 320 | soft | injected_timeout |
| TC-09 | Malformed retrieval output — missing metadata | insufficient_evidence | ✓ | ✓ | 2 | 1 | 240 | 80 | 320 | cascading_soft | OK |
| TC-10 | Infinite loop attempt — max steps detection | insufficient_evidence | ✓ | ✓ | 5 | 4 | 600 | 200 | 800 | soft | OK |
| TC-11 | Cache separation — legacy vs agent same message | unit_pass | ✓ | ✓ | 0 | 0 | 0 | 0 | 0 | - | Cache key separation verified |

## Aggregate Metrics

| Metric | Value |
|---|---|
| Task completion rate | 11/11 (100%) |
| Tool-call correctness rate | 11/11 (100%) |
| Mean iterations | 2.4 |
| Median iterations | 2 |
| Min/Max iterations | 1/5 |
| Mean search calls | 1.3 |
| Total tokens (all cases) | 4000 |
| Mean tokens per case | 363 |
| Hard failures | 1 |
| Soft failures | 2 |
| Cascading soft failures | 1 |

## Failure Taxonomy Notes

- **Hard failure**: unhandled exception, invalid response after repair, or fabricated answer after tool failure.
- **Soft failure**: safe but degraded result — extra search, conservative insufficient-evidence, or clarification when oracle expected direct answer.
- **Cascading soft failure**: an earlier degraded step propagates into later behavior but the final response remains safe.

## Failure Injection Observation (TC-08)

- Injected fault: retrieval timeout (ToolError raised in fake tool adapter)
- Expected behavior: tool failure recorded; no confident answer returned
- Observed status: `insufficient_evidence`
- Completion (safe outcome): ✓
- Failure records: ['tool_error(soft)']
- **Classification**: soft — the agent recognized the failure, recorded it in the trajectory, and did not produce a confident unsupported answer.

## Baseline Comparison Note

Multi-agent baseline comparison is not applicable — this implementation uses a single-agent design. Compared against the W15 legacy single-pass baseline: the baseline performs exactly 1 retrieval + 1 generation and cannot decide from intermediate evidence whether another source or clarification is needed. TC-02 (cross-source comparison) requires ≥ 2 searches and would be unsolvable by the baseline.