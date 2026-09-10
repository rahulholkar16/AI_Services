from langgraph.store.postgres.aio import AsyncPostgresStore
from app.rag.embeddings import get_embeddings
from app.utils.redis_util import cache_json_get, cache_json_set
import hashlib

EMBED_CACHE_TTL = 300  # 5 min: retrieve_memory's facts+episodes queries share the same text

def _embed_cache_key(text: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"embed_query:{digest}"

async def _embed_texts (texts: list[str]) -> list[list[float]]:
    embeddings = get_embeddings()
    results: list[list[float] | None] = [None] * len(texts)
    to_embed_idx = []
    to_embed_texts = []

    for i, text in enumerate(texts):
        cached = await cache_json_get(_embed_cache_key(text))
        if cached is not None:
            results[i] = cached
        else:
            to_embed_idx.append(i)
            to_embed_texts.append(text)

    if to_embed_texts:
        fresh = await embeddings.aembed_documents(to_embed_texts)
        for i, vec in zip(to_embed_idx, fresh):
            results[i] = vec
            await cache_json_set(_embed_cache_key(texts[i]), vec, ttl=EMBED_CACHE_TTL)

    return results

async def init_store(pool):
    return AsyncPostgresStore(
        pool,
        index={
            "embed": _embed_texts,
            "dims": 768,
            "fields": ["content"],
        },
    )