"""agent.py — Bounded cross-source verification agent.

Design note — Skill vs Agent:
    This capability could be packaged as a Skill for a fixed, reusable research
    procedure, but a Skill alone would not satisfy the requirement because the
    central behavior is runtime selection of the next search/clarification/final
    action from intermediate evidence; therefore the implementation uses an
    agent loop.

Design note — Single-agent choice:
    This task uses a single-agent loop, not multiple agents. One coherent
    decision-maker with a small bounded toolset is sufficient; adding verifier
    or researcher sub-agents would introduce a sequential coordination bottleneck
    and keep the source-grounding context split across boundaries, increasing
    token cost without needed specialization or isolation benefit.

Context Engineering:
    After each retrieval call the raw tool result is converted into a compact,
    deduplicated evidence ledger (EvidenceLedger). The raw payload is discarded
    and never forwarded to the next model call. The ledger is capped at
    AGENT_MAX_EVIDENCE_ITEMS and AGENT_MAX_EVIDENCE_CHARS. This prevents
    repeated cross-source searches from saturating the prompt with duplicate
    document chunks, which would cause the model to lose the original question
    or overlook a source conflict.
"""

from __future__ import annotations

import json
import logging
import re
import time
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator

from app.core.config import settings
from app.services import llm as llm_service
from app.services import tools as tool_service
from app.services.tools import ToolError

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Pydantic Contracts
# ═══════════════════════════════════════════════════════════════════════════════


class ActionEnum(str, Enum):
    SEARCH = "search"
    CLARIFY = "clarify"
    FINAL = "final"


class AgentAction(BaseModel):
    """Structured next action the model requests.

    Mutual exclusivity is enforced by the model_validator:
      - search  : non-empty query, no answer, no question
      - clarify : non-empty question, no answer, no query
      - final   : non-empty answer, at least one citation, no query/question
    """

    action: ActionEnum
    query: Optional[str] = Field(default=None, description="Search query (search only)")
    selected_sources: Optional[list[str]] = Field(
        default=None, description="Source filter (search only)"
    )
    top_k: int = Field(default=3, ge=1, le=10)
    question: Optional[str] = Field(default=None, description="Clarifying question (clarify only)")
    answer: Optional[str] = Field(default=None, description="Final answer text (final only)")
    citations: list[str] = Field(default_factory=list, description="Chunk IDs cited (final only)")

    @model_validator(mode="after")
    def _check_mutual_exclusivity(self) -> "AgentAction":
        if self.action == ActionEnum.SEARCH:
            if not self.query or not self.query.strip():
                raise ValueError("search action requires a non-empty query.")
            if self.answer:
                raise ValueError("search action must not include an answer.")
            if self.question:
                raise ValueError("search action must not include a question.")
        elif self.action == ActionEnum.CLARIFY:
            if not self.question or not self.question.strip():
                raise ValueError("clarify action requires a non-empty question.")
            if self.answer:
                raise ValueError("clarify action must not include an answer.")
        elif self.action == ActionEnum.FINAL:
            if not self.answer or not self.answer.strip():
                raise ValueError("final action requires a non-empty answer.")
            if self.query:
                raise ValueError("final action must not include a query.")
            if self.question:
                raise ValueError("final action must not include a question.")
        return self


class EvidenceItem(BaseModel):
    chunk_id: str
    source: str
    excerpt: str
    score: Optional[float] = None
    query: str  # the search query that retrieved this chunk


class TokenUsage(BaseModel):
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    by_provider: dict[str, Any] = Field(default_factory=dict)

    def add(self, usage_dict: dict) -> None:
        """Accumulate usage from a single model call's usage_dict."""
        inp = usage_dict.get("input_tokens")
        out = usage_dict.get("output_tokens")
        tot = usage_dict.get("total_tokens")
        provider = usage_dict.get("provider", "unknown")

        if inp is not None:
            self.input_tokens = (self.input_tokens or 0) + inp
        if out is not None:
            self.output_tokens = (self.output_tokens or 0) + out
        if tot is not None:
            self.total_tokens = (self.total_tokens or 0) + tot
        # Per-provider breakdown
        if provider not in self.by_provider:
            self.by_provider[provider] = {"input": 0, "output": 0, "total": 0}
        if inp is not None:
            self.by_provider[provider]["input"] += inp
        if out is not None:
            self.by_provider[provider]["output"] += out
        if tot is not None:
            self.by_provider[provider]["total"] += tot


class ToolCallEvent(BaseModel):
    iteration: int
    tool: str
    arguments: dict
    success: bool
    result_count: int = 0
    sources: list[str] = Field(default_factory=list)
    error: Optional[str] = None
    latency_ms: Optional[float] = None


class AgentStatusEnum(str, Enum):
    COMPLETED = "completed"
    NEEDS_CLARIFICATION = "needs_clarification"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    BOUNDED_FAILURE = "bounded_failure"


class AgentResponse(BaseModel):
    reply: str
    status: AgentStatusEnum
    sources: list[str] = Field(default_factory=list)
    iterations: int = 0
    tool_calls: list[ToolCallEvent] = Field(default_factory=list)
    failures: list[dict] = Field(default_factory=list)
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    model_used: str = "gemini"
    fallback_used: bool = False
    cache_hit: bool = False


# ═══════════════════════════════════════════════════════════════════════════════
# Internal state
# ═══════════════════════════════════════════════════════════════════════════════


class _AgentState:
    """Mutable accumulator for one agent request."""

    def __init__(self, question: str, requested_sources: Optional[list[str]]):
        self.question = question
        self.requested_sources = requested_sources  # None = all sources
        self.catalog: list[str] = []
        self.evidence: list[EvidenceItem] = []
        self.action_history: list[str] = []  # compact action summaries
        self.tool_calls: list[ToolCallEvent] = []
        self.failures: list[dict] = []
        self.token_usage = TokenUsage()
        self.iterations: int = 0
        self.search_count: int = 0
        self.repair_count: int = 0
        self.model_used: str = "gemini"
        self.fallback_used: bool = False
        self._last_search_signature: Optional[str] = None  # no-progress detection

    def record_failure(self, phase: str, iteration: int, error: str, taxonomy: str) -> None:
        self.failures.append(
            {
                "phase": phase,
                "iteration": iteration,
                "error": error,
                "taxonomy": taxonomy,  # hard | soft | cascading_soft
            }
        )

    def compact_evidence(self, new_chunks: list[dict]) -> int:
        """Add new chunks to the ledger, deduplicate, and enforce caps.

        Context Engineering — this is the compaction/clearing point:
          Input state: full raw Chroma result (list of chunk dicts)
          Output state: bounded, deduplicated EvidenceLedger entries
          Cap: AGENT_MAX_EVIDENCE_ITEMS items and AGENT_MAX_EVIDENCE_CHARS characters
          Deduplication key: chunk_id
          Token effect: raw payloads are discarded; only the compact ledger
            entries are forwarded to the next model decision prompt, preventing
            prompt saturation from repeated cross-source searches.
        """
        existing_ids = {e.chunk_id for e in self.evidence}
        added = 0
        for chunk in new_chunks:
            cid = str(chunk.get("chunk_id") or "").strip()
            src = str(chunk.get("source") or "").strip()
            if not cid or not src:
                self.record_failure(
                    "malformed_retrieval",
                    self.iterations,
                    "Retrieved chunk missing chunk_id or source metadata",
                    "cascading_soft",
                )
                continue
            if cid in existing_ids:
                continue
            if len(self.evidence) >= settings.agent_max_evidence_items:
                break
            total_chars = sum(len(e.excerpt) for e in self.evidence)
            excerpt = chunk.get("excerpt", "")
            if total_chars + len(excerpt) > settings.agent_max_evidence_chars:
                # Truncate excerpt to fit
                remaining = settings.agent_max_evidence_chars - total_chars
                if remaining < 50:
                    break
                excerpt = excerpt[:remaining]
            self.evidence.append(
                EvidenceItem(
                    chunk_id=cid,
                    source=src,
                    excerpt=excerpt,
                    score=chunk.get("score"),
                    query=chunk.get("query", ""),
                )
            )
            existing_ids.add(cid)
            added += 1
        return added

    def is_repeated_search(self, query: str, sources: Optional[list[str]]) -> bool:
        sig = f"{query.strip().lower()}|{sorted(sources or [])}"
        if sig == self._last_search_signature:
            return True
        self._last_search_signature = sig
        return False

    def ledger_text(self) -> str:
        """Compact evidence ledger for inclusion in the decision prompt."""
        if not self.evidence:
            return "(No evidence collected yet.)"
        lines = []
        for e in self.evidence:
            score_str = f" score={e.score}" if e.score is not None else ""
            lines.append(
                f"[{e.chunk_id}] source={e.source}{score_str}\n  {e.excerpt[:400]}"
            )
        return "\n\n".join(lines)

    def action_history_text(self) -> str:
        if not self.action_history:
            return "(No actions taken yet.)"
        return "\n".join(f"  {i+1}. {a}" for i, a in enumerate(self.action_history))


# ═══════════════════════════════════════════════════════════════════════════════
# System prompt for structured decisions
# ═══════════════════════════════════════════════════════════════════════════════

_SYSTEM_PROMPT = """You are a cross-source verification agent. Your job is to answer
the user's question by searching uploaded documents and verifying evidence.

You must respond with ONLY valid JSON matching this schema (no markdown, no explanation):
{
  "action": "search" | "clarify" | "final",
  "query": "<search query or null>",
  "selected_sources": ["<source name>", ...] or null,
  "top_k": <integer 1-5>,
  "question": "<clarifying question or null>",
  "answer": "<final answer or null>",
  "citations": ["<chunk_id>", ...]
}

Rules:
- "search": non-empty query, answer=null, question=null. Use selected_sources to filter.
- "clarify": non-empty question, answer=null, query=null. Use ONLY when the request is
  genuinely ambiguous or the available sources are insufficient to answer.
- "final": non-empty answer, citations list (chunk_ids from the ledger), query=null,
  question=null. ONLY cite chunk_ids that appear in the evidence ledger.
  Do NOT fabricate an answer if the evidence is insufficient.

You may search multiple times to compare sources. If evidence is insufficient after
searching, use "clarify" or produce a "final" answer that honestly states the limitation.
Do not produce a confident "final" answer without cited evidence.
"""


def _build_decision_prompt(state: _AgentState) -> str:
    sources_line = (
        f"Available sources: {state.catalog}" if state.catalog else "No sources available."
    )
    return (
        f"Question: {state.question}\n\n"
        f"{sources_line}\n\n"
        f"Evidence ledger:\n{state.ledger_text()}\n\n"
        f"Action history:\n{state.action_history_text()}\n\n"
        f"Remaining steps: {settings.agent_max_steps - state.iterations} of {settings.agent_max_steps}\n"
        f"Remaining searches: {settings.agent_max_searches - state.search_count} of {settings.agent_max_searches}\n\n"
        "Decide the next action."
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Action parsing and validation
# ═══════════════════════════════════════════════════════════════════════════════

def _extract_json(text: str) -> str:
    """Extract JSON object from model output, stripping markdown fences."""
    # Try to find a JSON block between ```...```
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        return fence.group(1)
    # Find the first {...} block
    brace = re.search(r"\{.*\}", text, re.DOTALL)
    if brace:
        return brace.group(0)
    return text


def _parse_action(text: str) -> AgentAction:
    """Parse and validate an AgentAction from raw model text.

    Raises ValueError on parse/validation failure so the caller can
    attempt one repair prompt.
    """
    raw_json = _extract_json(text)
    data = json.loads(raw_json)  # raises json.JSONDecodeError on bad JSON
    return AgentAction(**data)  # raises pydantic ValidationError on bad schema


# ═══════════════════════════════════════════════════════════════════════════════
# Main agent loop
# ═══════════════════════════════════════════════════════════════════════════════

async def run_agent(
    question: str,
    model_type: str = "gemini",
    temperature: float = 0.2,
    selected_sources: Optional[list[str]] = None,
    max_steps: Optional[int] = None,
    *,
    # Injectable adapters for testing (not used in production)
    _model_adapter=None,
    _tool_adapter=None,
) -> AgentResponse:
    """Bounded cross-source verification agent loop.

    Steps:
      1. Obtain source catalog and validate requested source filter.
      2. For up to MAX_STEPS iterations, ask the model for one structured action.
      3. Execute: search → compact evidence → loop; clarify → terminal;
         final → validate citations → terminal.
      4. Detect repeated no-progress searches and stop early.
      5. On malformed action, repair once; if still invalid, return bounded_failure.
      6. On tool failure, record and continue (model may try a different action).
      7. Return AgentResponse with full trajectory metadata.
    """
    # ── Resolve step limit ────────────────────────────────────────────────────
    server_max = settings.agent_max_steps
    effective_max = min(max_steps, server_max) if max_steps else server_max

    state = _AgentState(question=question, requested_sources=selected_sources)

    # ── Resolve adapters (production vs test) ─────────────────────────────────
    model_fn = _model_adapter if _model_adapter else llm_service.generate_structured_action
    tool_list_fn = _tool_adapter["list_sources"] if _tool_adapter else tool_service.list_sources
    tool_retrieve_fn = (
        _tool_adapter["retrieve_chunks"] if _tool_adapter else tool_service.retrieve_chunks
    )

    # ── Step 1: Obtain source catalog ─────────────────────────────────────────
    try:
        state.catalog = await tool_list_fn()
    except ToolError as e:
        state.record_failure("catalog", 0, str(e), "soft")
        state.catalog = []

    # Validate requested source filter
    if selected_sources is not None:
        unknown = [s for s in selected_sources if s not in state.catalog]
        if unknown and state.catalog:
            state.record_failure(
                "source_validation",
                0,
                f"Unknown sources: {unknown}",
                "soft",
            )
            # Filter to only known sources
            selected_sources = [s for s in selected_sources if s in state.catalog]
            state.requested_sources = selected_sources or None

    # ── Bounded loop ──────────────────────────────────────────────────────────
    for step in range(effective_max):
        state.iterations = step + 1

        # ── Ask model for next action ─────────────────────────────────────────
        prompt = _build_decision_prompt(state)
        repair_mode = False
        raw_text = ""
        action: Optional[AgentAction] = None
        usage: dict = {}

        try:
            raw_text, usage = await model_fn(prompt, _SYSTEM_PROMPT, temperature)
            state.token_usage.add(usage)
            if usage.get("provider", "gemini") != "gemini":
                state.fallback_used = True
                state.model_used = usage.get("provider", "ollama")
        except Exception as e:
            state.record_failure("model_call", state.iterations, str(e), "hard")
            break

        try:
            action = _parse_action(raw_text)
        except Exception as parse_err:
            # ── Repair attempt ────────────────────────────────────────────────
            if state.repair_count < settings.agent_max_invalid_action_repairs:
                state.repair_count += 1
                repair_mode = True
                state.record_failure(
                    "parse_action", state.iterations, str(parse_err), "soft"
                )
                repair_prompt = (
                    f"Your previous response was not valid JSON. Error: {parse_err}\n"
                    f"Raw output was: {raw_text[:200]}\n"
                    "Please respond with ONLY a valid JSON action object."
                )
                try:
                    raw_text2, usage2 = await model_fn(
                        repair_prompt, _SYSTEM_PROMPT, temperature
                    )
                    state.token_usage.add(usage2)
                    action = _parse_action(raw_text2)
                except Exception as repair_err:
                    state.record_failure(
                        "repair_action", state.iterations, str(repair_err), "hard"
                    )
                    break
            else:
                state.record_failure(
                    "parse_action", state.iterations, str(parse_err), "hard"
                )
                break

        if action is None:
            break

        # ── Execute action ────────────────────────────────────────────────────

        if action.action == ActionEnum.CLARIFY:
            # Terminal: clarification — no fabricated answer
            state.action_history.append(f"clarify: '{action.question}'")
            return AgentResponse(
                reply=action.question or "Could you please clarify your request?",
                status=AgentStatusEnum.NEEDS_CLARIFICATION,
                sources=[],
                iterations=state.iterations,
                tool_calls=state.tool_calls,
                failures=state.failures,
                token_usage=state.token_usage,
                model_used=state.model_used,
                fallback_used=state.fallback_used,
            )

        elif action.action == ActionEnum.FINAL:
            # Validate citations against ledger
            ledger_ids = {e.chunk_id for e in state.evidence}
            valid_citations = [c for c in action.citations if c in ledger_ids]
            invalid_citations = [c for c in action.citations if c not in ledger_ids]

            if invalid_citations:
                state.record_failure(
                    "invalid_citations",
                    state.iterations,
                    f"Citations not in ledger: {invalid_citations}",
                    "soft",
                )

            if not valid_citations:
                # No valid citations from ledger — convert to safe insufficient_evidence
                state.action_history.append("final (rejected: no valid citations)")
                return AgentResponse(
                    reply=(
                        "I was unable to find sufficient verified evidence in the available sources "
                        "to answer your question confidently."
                    ),
                    status=AgentStatusEnum.INSUFFICIENT_EVIDENCE,
                    sources=[],
                    iterations=state.iterations,
                    tool_calls=state.tool_calls,
                    failures=state.failures,
                    token_usage=state.token_usage,
                    model_used=state.model_used,
                    fallback_used=state.fallback_used,
                )

            cited_sources = list(
                {e.source for e in state.evidence if e.chunk_id in valid_citations}
            )
            state.action_history.append(
                f"final: {len(valid_citations)} citations from {cited_sources}"
            )
            return AgentResponse(
                reply=action.answer or "",
                status=AgentStatusEnum.COMPLETED,
                sources=cited_sources,
                iterations=state.iterations,
                tool_calls=state.tool_calls,
                failures=state.failures,
                token_usage=state.token_usage,
                model_used=state.model_used,
                fallback_used=state.fallback_used,
            )

        elif action.action == ActionEnum.SEARCH:
            # ── No-progress detection ─────────────────────────────────────────
            if state.is_repeated_search(action.query or "", action.selected_sources):
                state.record_failure(
                    "no_progress",
                    state.iterations,
                    f"Repeated search: '{action.query}'",
                    "soft",
                )
                break

            # ── Search count cap ──────────────────────────────────────────────
            if state.search_count >= settings.agent_max_searches:
                state.record_failure(
                    "search_cap",
                    state.iterations,
                    f"Reached max searches ({settings.agent_max_searches})",
                    "soft",
                )
                break

            state.search_count += 1
            effective_sources = action.selected_sources or state.requested_sources

            t0 = time.monotonic()
            try:
                chunks = await tool_retrieve_fn(
                    query=action.query or "",
                    selected_sources=effective_sources,
                    top_k=action.top_k,
                    catalog=state.catalog,
                )
                latency_ms = (time.monotonic() - t0) * 1000
                added = state.compact_evidence(chunks)
                state.action_history.append(
                    f"search('{action.query}', sources={effective_sources}): "
                    f"{len(chunks)} raw → {added} new evidence items"
                )
                unique_sources = list({c["source"] for c in chunks})
                state.tool_calls.append(
                    ToolCallEvent(
                        iteration=state.iterations,
                        tool="retrieve_chunks",
                        arguments={
                            "query": action.query,
                            "selected_sources": effective_sources,
                            "top_k": action.top_k,
                        },
                        success=True,
                        result_count=len(chunks),
                        sources=unique_sources,
                        latency_ms=round(latency_ms, 1),
                    )
                )
            except ToolError as te:
                latency_ms = (time.monotonic() - t0) * 1000
                state.record_failure(
                    "tool_error", state.iterations, str(te), "soft"
                )
                state.action_history.append(
                    f"search('{action.query}'): FAILED — {te.reason}"
                )
                state.tool_calls.append(
                    ToolCallEvent(
                        iteration=state.iterations,
                        tool="retrieve_chunks",
                        arguments={
                            "query": action.query,
                            "selected_sources": effective_sources,
                            "top_k": action.top_k,
                        },
                        success=False,
                        error=te.reason,
                        latency_ms=round(latency_ms, 1),
                    )
                )
                # Tool failure is recorded; model may adjust on next iteration.
                # We do NOT treat a failed/empty result as evidence.

    # ── Loop ended without a terminal action ─────────────────────────────────
    # Could be: max steps, max searches, no-progress, or hard failure.
    sources_cited = list({e.source for e in state.evidence})
    has_hard_failure = any(f["taxonomy"] == "hard" for f in state.failures)

    if has_hard_failure:
        status = AgentStatusEnum.BOUNDED_FAILURE
        reply = (
            "The agent reached its processing limit or encountered an unrecoverable "
            "error without collecting sufficient evidence to answer your question. "
            "Please try rephrasing or uploading more relevant documents."
        )
    else:
        status = AgentStatusEnum.INSUFFICIENT_EVIDENCE
        reply = (
            "After searching the available sources, I was unable to find conclusive "
            "evidence to answer your question. The collected evidence is available "
            "but does not provide a confident answer."
        )

    return AgentResponse(
        reply=reply,
        status=status,
        sources=sources_cited,
        iterations=state.iterations,
        tool_calls=state.tool_calls,
        failures=state.failures,
        token_usage=state.token_usage,
        model_used=state.model_used,
        fallback_used=state.fallback_used,
    )

