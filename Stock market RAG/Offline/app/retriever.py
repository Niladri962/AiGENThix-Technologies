"""Cosine-similarity retrieval from the persistent Chroma index. See section 6."""
from __future__ import annotations

from functools import lru_cache

import chromadb

from app.config import Settings, get_settings
from app.schemas import Chunk, RetrievedChunk
from ingest.embed import get_embedder


@lru_cache(maxsize=8)
def get_collection(chroma_dir: str, collection_name: str):
    """Shared, cached Chroma collection handle.

    Cached (not reopened per call) because chromadb's SQLite backend does not
    reliably tolerate two separate PersistentClient connections to the same
    path from one process; ingestion and retrieval must share this handle.
    """
    client = chromadb.PersistentClient(path=chroma_dir)
    return client.get_or_create_collection(collection_name, metadata={"hnsw:space": "cosine"})


@lru_cache(maxsize=8)
def _get_query_embedder(settings: Settings):
    return get_embedder(settings, for_query=True)


def retrieve(query: str, k: int) -> list[RetrievedChunk]:
    settings = get_settings()
    embedder = _get_query_embedder(settings)
    collection = get_collection(settings.chroma_dir, settings.collection)

    if collection.count() == 0:
        return []

    [query_embedding] = embedder.embed([query])
    k = min(k, collection.count())
    result = collection.query(query_embeddings=[query_embedding], n_results=k)

    retrieved: list[RetrievedChunk] = []
    ids = result["ids"][0]
    for i in range(len(ids)):
        meta = result["metadatas"][0][i]
        distance = result["distances"][0][i]
        score = 1.0 - distance  # cosine distance -> cosine similarity
        chunk = Chunk(
            chunk_id=ids[i],
            doc_id=meta["doc_id"],
            title=meta["title"],
            publisher=meta["publisher"],
            url=meta["url"],
            page=meta["page"],
            section=meta["section"],
            text=result["documents"][0][i],
        )
        retrieved.append(RetrievedChunk(chunk=chunk, score=score))

    retrieved.sort(key=lambda rc: rc.score, reverse=True)
    return retrieved


def collection_count(settings: Settings | None = None) -> int:
    settings = settings or get_settings()
    return get_collection(settings.chroma_dir, settings.collection).count()
