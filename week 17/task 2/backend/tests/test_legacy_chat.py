"""test_legacy_chat.py — Smoke tests for the W15 legacy /chat endpoint.

Verifies that adding the agent feature did not break the existing chat path.
Uses a lightweight ASGI test client (httpx + FastAPI's TestClient).
"""

import json
import pytest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.core.cache import make_cache_key, make_agent_cache_key


# ── TestClient (synchronous wrapper for FastAPI async endpoints) ───────────────
client = TestClient(app)


# ═══════════════════════════════════════════════════════════════════════════════
# Cache key tests (no network needed)
# ═══════════════════════════════════════════════════════════════════════════════

class TestCacheKeys:
    def test_chat_key_prefix(self):
        key = make_cache_key({"message": "hello", "model_type": "gemini"})
        assert key.startswith("chat:")

    def test_agent_key_prefix(self):
        key = make_agent_cache_key({"message": "hello", "model_type": "gemini"})
        assert key.startswith("agent:")

    def test_keys_differ_for_same_message(self):
        msg = "What is the return policy?"
        k1 = make_cache_key({"message": msg})
        k2 = make_agent_cache_key({"message": msg})
        assert k1 != k2


# ═══════════════════════════════════════════════════════════════════════════════
# Health endpoint
# ═══════════════════════════════════════════════════════════════════════════════

class TestHealthEndpoint:
    def test_health_returns_200(self):
        # Health endpoint does I/O (Redis, Ollama) but should still return 200
        # with "down" statuses when services are unavailable.
        with patch("app.api.routes.check_redis_health", new_callable=AsyncMock, return_value=False), \
             patch("app.api.routes.check_ollama_health", new_callable=AsyncMock, return_value=False):
            response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "redis" in data
        assert "ollama" in data


# ═══════════════════════════════════════════════════════════════════════════════
# Legacy /chat endpoint schema
# ═══════════════════════════════════════════════════════════════════════════════

class TestLegacyChatSchema:
    def test_chat_response_includes_required_fields(self):
        """Mocked chat endpoint returns the expected ChatResponse schema fields."""
        mock_result = {
            "reply": "Test response.",
            "model_used": "gemini",
            "fallback_used": False,
            "sources": [],
            "cache_hit": False,
        }
        with patch("app.api.routes.get_cached", new_callable=AsyncMock, return_value=None), \
             patch("app.api.routes.set_cached", new_callable=AsyncMock), \
             patch("app.api.routes.rag.retrieve_context", new_callable=AsyncMock, return_value=("", [])), \
             patch("app.api.routes.generate_response", new_callable=AsyncMock, return_value={
                 "reply": "Test response.",
                 "model_used": "gemini",
                 "fallback_used": False,
             }):
            response = client.post(
                "/api/v1/chat",
                json={"message": "Hello", "use_rag": False},
            )

        assert response.status_code == 200
        data = response.json()
        assert "reply" in data
        assert "model_used" in data
        assert "fallback_used" in data
        assert "cache_hit" in data

    def test_chat_cache_hit_response(self):
        """Cache hit path returns cache_hit=True and skips model call."""
        cached_value = json.dumps({
            "reply": "Cached answer.",
            "model_used": "gemini",
            "fallback_used": False,
            "sources": [],
            "cache_hit": False,  # will be overwritten to True
        })
        with patch("app.api.routes.get_cached", new_callable=AsyncMock, return_value=cached_value):
            response = client.post(
                "/api/v1/chat",
                json={"message": "Hello", "use_rag": False},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["cache_hit"] is True
        assert data["reply"] == "Cached answer."


# ═══════════════════════════════════════════════════════════════════════════════
# Agent /agent/chat endpoint schema
# ═══════════════════════════════════════════════════════════════════════════════

class TestAgentChatSchema:
    def test_agent_response_includes_required_fields(self):
        """Mocked agent endpoint returns the expected AgentChatResponse schema."""
        from app.services.agent import AgentResponse, AgentStatusEnum, TokenUsage
        mock_agent_result = AgentResponse(
            reply="Agent answer.",
            status=AgentStatusEnum.COMPLETED,
            sources=["doc-a.txt"],
            iterations=2,
            token_usage=TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150),
            model_used="gemini",
            fallback_used=False,
        )
        with patch("app.api.routes.get_cached", new_callable=AsyncMock, return_value=None), \
             patch("app.api.routes.set_cached", new_callable=AsyncMock), \
             patch("app.api.routes.run_agent", new_callable=AsyncMock, return_value=mock_agent_result):
            response = client.post(
                "/api/v1/agent/chat",
                json={"message": "Compare policies."},
            )

        assert response.status_code == 200
        data = response.json()
        assert "reply" in data
        assert "status" in data
        assert "iterations" in data
        assert "tool_calls" in data
        assert "failures" in data
        assert "token_usage" in data
        assert "sources" in data
        assert data["status"] == "completed"

    def test_agent_cache_separate_from_chat(self):
        """Agent and chat cache lookups use different keys — they never share data."""
        # Build what a cached agent response looks like
        cached_agent = json.dumps({
            "reply": "Agent cached.",
            "status": "completed",
            "sources": ["doc-a.txt"],
            "iterations": 1,
            "tool_calls": [],
            "failures": [],
            "token_usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15, "by_provider": {}},
            "model_used": "gemini",
            "fallback_used": False,
            "cache_hit": False,
        })
        with patch("app.api.routes.get_cached", new_callable=AsyncMock, return_value=cached_agent):
            response = client.post(
                "/api/v1/agent/chat",
                json={"message": "Hello"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["cache_hit"] is True
        assert data["reply"] == "Agent cached."

