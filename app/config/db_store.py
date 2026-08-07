from langgraph.store.postgres.aio import AsyncPostgresStore
from app.rag.embeddings import get_embeddings

async def _embed_texts (texts: list[str]) -> list[list[float]]:
    embeddings = get_embeddings()
    return await embeddings.aembed_documents(texts)

async def init_store(pool):
    return AsyncPostgresStore(
        pool,
        index={
            "embed": _embed_texts,
            "dims": 768,
            "fields": ["content"],
        },
    )