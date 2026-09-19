"""tools.py — Bounded tool registry for the agent.

Provides two agent-facing tools:
  1. list_sources()       — returns catalog of ingested source names
  2. retrieve_chunks()    — validated, bounded retrieval returning EvidenceItem dicts

These wrappers validate all arguments (source names against catalog, top_k cap,
query length cap) BEFORE calling the underlying Chroma retrieval, so the model
can never trigger unbounded searches or inject unknown sources.
"""

import asyncio
import logging
from typing import Optional

from app.core.config import settings
from app.services import rag as rag_service

logger = logging.getLogger(__name__)


class ToolError(Exception):
    """Raised when a tool call fails in a structured, recordable way."""

    def __init__(self, tool: str, reason: str):
        self.tool = tool
        self.reason = reason
        super().__init__(f"[{tool}] {reason}")


async def list_sources() -> list[str]:
    """Return all source names currently available in the knowledge base.

    Returns an empty list (not an error) when no documents have been ingested.
    """
    try:
        return await asyncio.wait_for(
            rag_service.list_available_sources(),
            timeout=settings.agent_tool_timeout_seconds,
        )
    except asyncio.TimeoutError:
        raise ToolError("list_sources", "Timed out querying source catalog.")
    except Exception as e:
        raise ToolError("list_sources", str(e))


async def retrieve_chunks(
    query: str,
    selected_sources: Optional[list[str]],
    top_k: int,
    catalog: list[str],
) -> list[dict]:
    """Retrieve structured evidence chunks from the knowledge base.

    Arguments are validated before any Chroma call:
      - query must be non-empty and within AGENT_MAX_QUERY_CHARS
      - top_k is capped to AGENT_TOP_K_MAX (client value is silently reduced)
      - every requested source name must exist in catalog; unknown names raise ToolError

    Returns a list of dicts compatible with EvidenceItem:
      {chunk_id, source, excerpt, score, query}

    Empty retrieval (no matching chunks) returns [] — this is valid evidence
    that no relevant content was found, NOT permission to invent an answer.
    """
    # ── Validate query ────────────────────────────────────────────────────────
    if not query or not query.strip():
        raise ToolError("retrieve_chunks", "Query must be a non-empty string.")
    if len(query) > settings.agent_max_query_chars:
        raise ToolError(
            "retrieve_chunks",
            f"Query length {len(query)} exceeds limit {settings.agent_max_query_chars}.",
        )

    # ── Validate sources ──────────────────────────────────────────────────────
    if selected_sources is not None:
        unknown = [s for s in selected_sources if s not in catalog]
        if unknown:
            raise ToolError(
                "retrieve_chunks",
                f"Unknown sources: {unknown}. Available: {catalog}",
            )

    # ── Cap top_k ─────────────────────────────────────────────────────────────
    safe_top_k = min(max(1, top_k), settings.agent_top_k_max)

    # ── Call retrieval with timeout ───────────────────────────────────────────
    try:
        chunks = await asyncio.wait_for(
            rag_service.retrieve_chunks_structured(
                query=query.strip(),
                top_k=safe_top_k,
                selected_sources=selected_sources,
            ),
            timeout=settings.agent_tool_timeout_seconds,
        )
        return chunks
    except asyncio.TimeoutError:
        raise ToolError(
            "retrieve_chunks",
            f"Retrieval timed out after {settings.agent_tool_timeout_seconds}s.",
        )
    except Exception as e:
        raise ToolError("retrieve_chunks", str(e))

