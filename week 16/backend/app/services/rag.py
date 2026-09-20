import chromadb
import asyncio
import logging
from google import genai
from app.core.config import settings

logger = logging.getLogger(__name__)

_chroma_client = None
_collection = None
_genai_client = None


def get_chroma():
    global _chroma_client, _collection
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=settings.chroma_db_dir)
        _collection = _chroma_client.get_or_create_collection(name="documents")
    return _collection


def get_genai():
    global _genai_client
    if _genai_client is None and settings.gemini_api_key:
        _genai_client = genai.Client(api_key=settings.gemini_api_key)
    return _genai_client


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200):
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start : start + chunk_size])
        start += chunk_size - overlap
    return chunks


async def embed(text: str) -> list:
    client = get_genai()
    if not client:
        raise ValueError("GEMINI_API_KEY not set.")
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: client.models.embed_content(model="gemini-embedding-2", contents=text),
    )
    return response.embeddings[0].values


async def embed_many(texts: list[str]) -> list[list[float]]:
    """Embed chunks in batches so ingestion does not make one API call per chunk."""
    client = get_genai()
    if not client:
        raise ValueError("GEMINI_API_KEY not set.")
    loop = asyncio.get_event_loop()
    embeddings = []
    for start in range(0, len(texts), 100):
        batch = texts[start : start + 100]
        response = await loop.run_in_executor(
            None,
            lambda batch=batch: client.models.embed_content(
                model="gemini-embedding-2", contents=batch
            ),
        )
        batch_embeddings = [item.values for item in response.embeddings]
        if len(batch_embeddings) == len(batch):
            embeddings.extend(batch_embeddings)
            continue

        # Some SDK/model combinations treat a list as one content item. Never
        # pass a partial embedding list to Chroma; recover one vector per chunk.
        logger.warning(
            "Embedding batch returned %s vectors for %s chunks; retrying individually.",
            len(batch_embeddings),
            len(batch),
        )
        semaphore = asyncio.Semaphore(8)

        async def embed_with_limit(chunk: str) -> list:
            async with semaphore:
                return await embed(chunk)

        individual_embeddings = await asyncio.gather(
            *(embed_with_limit(chunk) for chunk in batch)
        )
        embeddings.extend(individual_embeddings)

    if len(embeddings) != len(texts):
        raise RuntimeError(
            f"Embedding count mismatch: expected {len(texts)}, got {len(embeddings)}."
        )
    return embeddings


async def ingest_text(text: str, source_name: str = "upload") -> int:
    collection = get_chroma()
    chunks = chunk_text(text)
    if not chunks:
        return 0

    embeddings = await embed_many(chunks)

    # Replace a previous upload with the same filename instead of leaving stale chunks.
    collection.delete(where={"source": source_name})
    ids = [f"{source_name}_{i}" for i in range(len(chunks))]
    metadatas = [{"source": source_name} for _ in chunks]
    collection.add(embeddings=embeddings, documents=chunks, metadatas=metadatas, ids=ids)
    return len(chunks)


async def clear_collection() -> None:
    """Remove all persisted document chunks from the knowledge base."""
    collection = get_chroma()
    if collection.count():
        collection.delete(ids=collection.get(include=[])["ids"])


async def retrieve_context(
    query: str,
    top_k: int = 3,
    selected_sources: list[str] | None = None,
) -> tuple[str, list]:
    """Legacy retrieval returning (context_string, sources_list).

    Preserved for the existing /api/v1/chat endpoint. Do not change the
    return signature — the agent uses retrieve_chunks() in tools.py instead.
    """
    collection = get_chroma()
    if collection.count() == 0:
        return "", []
    if selected_sources is not None and len(selected_sources) == 0:
        return "", []

    query_embedding = await embed(query)
    query_kwargs = {"query_embeddings": [query_embedding], "n_results": top_k}
    if selected_sources:
        query_kwargs["where"] = {"source": {"$in": selected_sources}}

    results = collection.query(**query_kwargs)
    context = ""
    sources = []
    if results and results["documents"] and results["documents"][0]:
        for i, doc in enumerate(results["documents"][0]):
            src = results["metadatas"][0][i]["source"]
            sources.append(src)
            context += f"[{src}]: {doc}\n\n"
    return context.strip(), list(set(sources))


async def retrieve_chunks_structured(
    query: str,
    top_k: int = 3,
    selected_sources: list[str] | None = None,
) -> list[dict]:
    """Agent-facing retrieval returning structured chunk records.

    Returns a list of dicts with keys: chunk_id, source, excerpt, score, query.
    Used by tools.py to build EvidenceItem records without exposing raw Chroma
    output to subsequent decision prompts.
    """
    collection = get_chroma()
    if collection.count() == 0:
        return []
    if selected_sources is not None and len(selected_sources) == 0:
        return []

    query_embedding = await embed(query)
    query_kwargs: dict = {
        "query_embeddings": [query_embedding],
        "n_results": min(top_k, collection.count()),
        "include": ["documents", "metadatas", "distances"],
    }
    if selected_sources:
        query_kwargs["where"] = {"source": {"$in": selected_sources}}

    results = collection.query(**query_kwargs)
    chunks = []
    if results and results["documents"] and results["documents"][0]:
        docs = results["documents"][0]
        metas = results["metadatas"][0]
        ids = results["ids"][0]
        distances = results.get("distances", [[None] * len(docs)])[0]
        for i, doc in enumerate(docs):
            score = None
            if distances[i] is not None:
                # Chroma returns L2 distance; convert to a rough similarity proxy
                score = round(1.0 / (1.0 + distances[i]), 4)
            chunks.append(
                {
                    "chunk_id": ids[i],
                    "source": metas[i].get("source", "unknown"),
                    "excerpt": doc,
                    "score": score,
                    "query": query,
                }
            )
    return chunks


async def list_available_sources() -> list[str]:
    """Return all unique source names currently stored in Chroma."""
    collection = get_chroma()
    if collection.count() == 0:
        return []
    try:
        # Fetch all metadatas (may be large in production; bounded by collection size)
        results = collection.get(include=["metadatas"])
        sources = set()
        for meta in results.get("metadatas", []):
            if meta and "source" in meta:
                sources.add(meta["source"])
        return sorted(sources)
    except Exception as e:
        logger.warning(f"list_available_sources failed: {e}")
        return []
