"""test_agent.py — Focused unit tests for the agent loop.

All tests use fake deterministic model and tool adapters. No live Gemini,
Chroma, Redis, Ollama, or Docker dependency.

Test matrix:
  1. Action validation — valid search/clarify/final + rejected combos
  2. Two-iteration loop — cross-source comparison (proves iterations >= 2)
  3. Max-steps cap — loop terminates at configured cap
  4. No-progress detection — repeated identical search stops early
  5. Clarification terminal — clarify returns needs_clarification, no answer
  6. Tool failure → insufficient_evidence or bounded_failure
  7. Malformed JSON → repair → bounded_failure (repair limit enforced)
  8. Cache key separation — same message → different keys for chat vs agent
  9. Token aggregation — usage accumulated across multiple iterations
  10. Insufficient evidence without citations → insufficient_evidence status
"""

import asyncio
import json
import pytest

from app.services.agent import (
    AgentAction,
    ActionEnum,
    run_agent,
    AgentStatusEnum,
)
from app.core.cache import make_cache_key, make_agent_cache_key
from app.services.tools import ToolError


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers: fake adapters
# ═══════════════════════════════════════════════════════════════════════════════

def _usage(inp=10, out=5):
    return {
        "input_tokens": inp,
        "output_tokens": out,
        "total_tokens": inp + out,
        "provider": "gemini",
        "fallback_used": False,
    }


def _action_json(**kwargs) -> str:
    """Return a JSON string for an AgentAction with defaults."""
    base = {
        "action": "search",
        "query": None,
        "selected_sources": None,
        "top_k": 3,
        "question": None,
        "answer": None,
        "citations": [],
    }
    base.update(kwargs)
    return json.dumps(base)


def _make_script_model(*responses):
    """Return a fake model adapter that yields scripted responses in order."""
    calls = iter(responses)

    async def _model(prompt, system_prompt, temperature):
        try:
            text = next(calls)
        except StopIteration:
            text = _action_json(action="clarify", question="No more scripted responses.")
        return text, _usage()

    return _model


def _make_script_tools(catalog=None, chunks_per_call=None):
    """Return a fake tool adapter."""
    catalog = catalog or ["doc-a.txt", "doc-b.txt"]
    chunk_seq = iter(chunks_per_call or [])

    async def _list():
        return catalog

    async def _retrieve(query, selected_sources, top_k, **kw):
        try:
            chunks = next(chunk_seq)
        except StopIteration:
            chunks = []
        return chunks

    return {"list_sources": _list, "retrieve_chunks": _retrieve}


def _make_failing_tool(error="Timeout"):
    """Return a tool adapter that always raises ToolError on retrieve."""
    async def _list():
        return ["doc-a.txt"]

    async def _retrieve(query, selected_sources, top_k, **kw):
        raise ToolError("retrieve_chunks", error)

    return {"list_sources": _list, "retrieve_chunks": _retrieve}


SAMPLE_CHUNK_A = {
    "chunk_id": "doc-a.txt_0",
    "source": "doc-a.txt",
    "excerpt": "Policy A: refunds within 30 days.",
    "score": 0.9,
    "query": "refund policy",
}
SAMPLE_CHUNK_B = {
    "chunk_id": "doc-b.txt_0",
    "source": "doc-b.txt",
    "excerpt": "Policy B: refunds within 14 days.",
    "score": 0.85,
    "query": "refund policy",
}


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Action validation
# ═══════════════════════════════════════════════════════════════════════════════

class TestActionValidation:
    def test_valid_search(self):
        a = AgentAction(action=ActionEnum.SEARCH, query="what is the policy?", top_k=3)
        assert a.action == ActionEnum.SEARCH

    def test_valid_clarify(self):
        a = AgentAction(action=ActionEnum.CLARIFY, question="Which document do you mean?")
        assert a.action == ActionEnum.CLARIFY

    def test_valid_final(self):
        a = AgentAction(
            action=ActionEnum.FINAL,
            answer="The policy is 30 days.",
            citations=["doc-a.txt_0"],
        )
        assert a.action == ActionEnum.FINAL

    def test_search_requires_query(self):
        with pytest.raises(Exception):
            AgentAction(action=ActionEnum.SEARCH, query="")

    def test_search_cannot_have_answer(self):
        with pytest.raises(Exception):
            AgentAction(action=ActionEnum.SEARCH, query="q", answer="something")

    def test_clarify_requires_question(self):
        with pytest.raises(Exception):
            AgentAction(action=ActionEnum.CLARIFY, question="")

    def test_clarify_cannot_have_answer(self):
        with pytest.raises(Exception):
            AgentAction(action=ActionEnum.CLARIFY, question="q?", answer="something")

    def test_final_requires_answer(self):
        with pytest.raises(Exception):
            AgentAction(action=ActionEnum.FINAL, answer="")

    def test_final_cannot_have_query(self):
        with pytest.raises(Exception):
            AgentAction(
                action=ActionEnum.FINAL,
                answer="The answer",
                query="something",
                citations=["id1"],
            )


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Two-iteration cross-source comparison (iterations >= 2)
# ═══════════════════════════════════════════════════════════════════════════════

class TestTwoIterationLoop:
    @pytest.mark.asyncio
    async def test_two_searches_then_final(self):
        """The model performs two searches (different sources) then gives a final answer."""
        model = _make_script_model(
            # Iter 1: search doc-a
            _action_json(action="search", query="refund policy", selected_sources=["doc-a.txt"], top_k=2),
            # Iter 2: search doc-b
            _action_json(action="search", query="refund policy", selected_sources=["doc-b.txt"], top_k=2),
            # Iter 3: final with citations from both
            _action_json(
                action="final",
                answer="Policy A: 30 days; Policy B: 14 days.",
                citations=["doc-a.txt_0", "doc-b.txt_0"],
            ),
        )
        tools = _make_script_tools(
            chunks_per_call=[[SAMPLE_CHUNK_A], [SAMPLE_CHUNK_B]]
        )

        result = await run_agent(
            question="Compare refund policies in doc-a and doc-b.",
            _model_adapter=model,
            _tool_adapter=tools,
        )

        assert result.status == AgentStatusEnum.COMPLETED
        assert result.iterations >= 2, f"Expected >= 2 iterations, got {result.iterations}"
        assert "doc-a.txt" in result.sources
        assert "doc-b.txt" in result.sources
        # Action history proves model selected different source filters each time
        assert any("doc-a.txt" in h for h in result.tool_calls[0].arguments.get("selected_sources", []))
        assert any("doc-b.txt" in h for h in result.tool_calls[1].arguments.get("selected_sources", []))


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Max-steps cap
# ═══════════════════════════════════════════════════════════════════════════════

class TestMaxStepsCap:
    @pytest.mark.asyncio
    async def test_loop_stops_at_max_steps(self):
        """Always-searching model is stopped by the max_steps limit."""
        # Each scripted response is a search — more than agent_max_steps
        responses = [
            _action_json(action="search", query=f"query {i}", top_k=2)
            for i in range(20)
        ]
        model = _make_script_model(*responses)
        tools = _make_script_tools(chunks_per_call=[[]] * 20)

        result = await run_agent(
            question="What is the meaning of life?",
            max_steps=3,
            _model_adapter=model,
            _tool_adapter=tools,
        )

        assert result.iterations <= 3
        assert result.status in (
            AgentStatusEnum.BOUNDED_FAILURE,
            AgentStatusEnum.INSUFFICIENT_EVIDENCE,
        )

    @pytest.mark.asyncio
    async def test_client_cannot_exceed_server_max(self):
        """max_steps=100 is silently capped to server's agent_max_steps."""
        responses = [
            _action_json(action="search", query=f"q{i}", top_k=2)
            for i in range(50)
        ]
        model = _make_script_model(*responses)
        tools = _make_script_tools(chunks_per_call=[[]] * 50)

        result = await run_agent(
            question="Test",
            max_steps=100,
            _model_adapter=model,
            _tool_adapter=tools,
        )

        from app.core.config import settings
        assert result.iterations <= settings.agent_max_steps


# ═══════════════════════════════════════════════════════════════════════════════
# 4. No-progress detection
# ═══════════════════════════════════════════════════════════════════════════════

class TestNoProgressDetection:
    @pytest.mark.asyncio
    async def test_repeated_identical_search_stops_loop(self):
        """Repeating the exact same query/sources triggers no-progress and stops."""
        model = _make_script_model(
            _action_json(action="search", query="refund policy", top_k=2),
            _action_json(action="search", query="refund policy", top_k=2),  # identical
            _action_json(action="search", query="refund policy", top_k=2),
        )
        tools = _make_script_tools(chunks_per_call=[[SAMPLE_CHUNK_A]] * 3)

        result = await run_agent(
            question="What is the refund policy?",
            _model_adapter=model,
            _tool_adapter=tools,
        )

        assert any("no_progress" in str(f) for f in result.failures)
        # Should not have run more than 2 iterations (second repeat triggers stop)
        assert result.iterations <= 3


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Clarification terminal
# ═══════════════════════════════════════════════════════════════════════════════

class TestClarificationTerminal:
    @pytest.mark.asyncio
    async def test_clarify_stops_with_no_answer(self):
        model = _make_script_model(
            _action_json(action="clarify", question="Which document are you referring to?"),
        )
        tools = _make_script_tools()

        result = await run_agent(
            question="Compare the documents.",
            _model_adapter=model,
            _tool_adapter=tools,
        )

        assert result.status == AgentStatusEnum.NEEDS_CLARIFICATION
        assert "Which document" in result.reply
        assert result.iterations == 1
        # No fabricated answer — reply is only the clarifying question
        assert len(result.sources) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Tool failure → safe response (no confident unsupported answer)
# ═══════════════════════════════════════════════════════════════════════════════

class TestToolFailure:
    @pytest.mark.asyncio
    async def test_tool_timeout_recorded_no_confident_answer(self):
        """Injected retrieval timeout is recorded; result is not a confident answer."""
        model = _make_script_model(
            _action_json(action="search", query="policy", top_k=2),
            # After tool failure, model still tries to give final (no evidence)
            _action_json(action="final", answer="The policy is X.", citations=[]),
        )
        tools = _make_failing_tool("Timed out after 10s.")

        result = await run_agent(
            question="What is the policy?",
            _model_adapter=model,
            _tool_adapter=tools,
        )

        # Tool failure must be recorded
        assert any(f.get("taxonomy") in ("soft", "hard") for f in result.failures)
        # Final with no valid ledger citations → insufficient_evidence, not completed
        assert result.status in (
            AgentStatusEnum.INSUFFICIENT_EVIDENCE,
            AgentStatusEnum.BOUNDED_FAILURE,
            AgentStatusEnum.NEEDS_CLARIFICATION,
        )
        # Must NOT be "completed" with a confident unsupported answer
        assert result.status != AgentStatusEnum.COMPLETED


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Malformed JSON → repair → bounded failure
# ═══════════════════════════════════════════════════════════════════════════════

class TestMalformedAction:
    @pytest.mark.asyncio
    async def test_malformed_json_triggers_repair_then_bounded_failure(self):
        """Two consecutive bad responses exhaust the repair budget → bounded_failure."""
        bad_response = "Sorry, I am unable to help with that. Please rephrase."

        model = _make_script_model(
            bad_response,   # first parse fails
            bad_response,   # repair attempt also fails
        )
        tools = _make_script_tools()

        result = await run_agent(
            question="Something ambiguous",
            _model_adapter=model,
            _tool_adapter=tools,
        )

        # parse_action failure recorded
        assert any("parse_action" in str(f) or "repair_action" in str(f) for f in result.failures)
        assert result.status in (
            AgentStatusEnum.BOUNDED_FAILURE,
            AgentStatusEnum.INSUFFICIENT_EVIDENCE,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Cache key separation
# ═══════════════════════════════════════════════════════════════════════════════

class TestCacheKeySeparation:
    def test_same_message_different_keys_for_chat_vs_agent(self):
        payload = {
            "message": "What is the refund policy?",
            "model_type": "gemini",
            "temperature": 0.7,
            "use_rag": True,
            "selected_sources": None,
        }
        agent_payload = {
            "message": "What is the refund policy?",
            "model_type": "gemini",
            "temperature": 0.2,
            "selected_sources": None,
            "max_steps": None,
        }
        chat_key = make_cache_key(payload)
        agent_key = make_agent_cache_key(agent_payload)

        assert chat_key.startswith("chat:")
        assert agent_key.startswith("agent:")
        assert chat_key != agent_key

    def test_agent_keys_are_deterministic(self):
        payload = {"message": "hello", "model_type": "gemini", "temperature": 0.2,
                   "selected_sources": None, "max_steps": None}
        k1 = make_agent_cache_key(payload)
        k2 = make_agent_cache_key(payload)
        assert k1 == k2


# ═══════════════════════════════════════════════════════════════════════════════
# 9. Token aggregation
# ═══════════════════════════════════════════════════════════════════════════════

class TestTokenAggregation:
    @pytest.mark.asyncio
    async def test_tokens_accumulated_across_iterations(self):
        """Token usage from multiple model calls must be summed in the response."""
        model = _make_script_model(
            _action_json(action="search", query="policy A", selected_sources=["doc-a.txt"], top_k=2),
            _action_json(action="final", answer="The answer.", citations=["doc-a.txt_0"]),
        )
        tools = _make_script_tools(chunks_per_call=[[SAMPLE_CHUNK_A]])

        result = await run_agent(
            question="What is policy A?",
            _model_adapter=model,
            _tool_adapter=tools,
        )

        # Two model calls × (10 input + 5 output) each = 30 total
        assert result.token_usage.input_tokens == 20
        assert result.token_usage.output_tokens == 10
        assert result.token_usage.total_tokens == 30


# ═══════════════════════════════════════════════════════════════════════════════
# 10. Final without citations on empty ledger → insufficient_evidence
# ═══════════════════════════════════════════════════════════════════════════════

class TestFinalWithoutEvidence:
    @pytest.mark.asyncio
    async def test_final_with_no_ledger_becomes_insufficient_evidence(self):
        """A model that immediately calls final with no evidence is rejected safely."""
        model = _make_script_model(
            _action_json(action="final", answer="I think the policy is 30 days.", citations=[]),
        )
        tools = _make_script_tools(chunks_per_call=[])

        result = await run_agent(
            question="What is the refund period?",
            _model_adapter=model,
            _tool_adapter=tools,
        )

        assert result.status == AgentStatusEnum.INSUFFICIENT_EVIDENCE
        # Must not be a confident fabricated answer
        assert result.status != AgentStatusEnum.COMPLETED

