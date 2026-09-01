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


async def ingest_text(text: str, source_name: str = "upload") -> int:
    collection = get_chroma()
    chunks = chunk_text(text)
    if not chunks:
        return 0

    embeddings = []
    for chunk in chunks:
        embeddings.append(await embed(chunk))

    ids = [f"{source_name}_{i}" for i in range(len(chunks))]
    metadatas = [{"source": source_name} for _ in chunks]
    collection.add(embeddings=embeddings, documents=chunks, metadatas=metadatas, ids=ids)
    return len(chunks)


async def retrieve_context(query: str, top_k: int = 3, selected_sources: list[str] | None = None) -> tuple[str, list]:
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
