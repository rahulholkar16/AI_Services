import os
import asyncio
import logging
from pinecone import PineconeAsyncio, ServerlessSpec

logger = logging.getLogger(__name__)

INDEX_NAME = "github-repo"
DIMENSION = 768

_pc: PineconeAsyncio | None = None
_index_async = None


def _get_client() -> PineconeAsyncio:
    global _pc
    if _pc is None:
        _pc = PineconeAsyncio(api_key=os.getenv("PINECONE_API_KEY"))
    return _pc


async def _ensure_index_exists() -> None:
    pc = _get_client()
    existing = [i.name for i in await pc.list_indexes()]
    if INDEX_NAME in existing:
        logger.debug("Index exists: %s", INDEX_NAME)
        return

    await pc.create_index(
        name=INDEX_NAME,
        dimension=DIMENSION,
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1"),
    )

    while True:
        desc = await pc.describe_index(INDEX_NAME)
        if desc.status["ready"]:
            break
        await asyncio.sleep(2)
    logger.info("Index ready!")


async def get_index():
    global _index_async
    if _index_async is None:
        await _ensure_index_exists()
        pc = _get_client()
        desc = await pc.describe_index(INDEX_NAME)
        _index_async = pc.IndexAsyncio(host=desc.host)
    return _index_async


async def close_index() -> None:
    global _pc, _index_async
    if _index_async is not None:
        await _index_async.close()
        _index_async = None
    if _pc is not None:
        await _pc.close()
        _pc = None
