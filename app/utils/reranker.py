import os
import logging
import cohere

logger = logging.getLogger(__name__)

COHERE_API_KEY = os.getenv("COHERE_API_KEY")
_client: cohere.AsyncClientV2 | None = None


def _get_client() -> cohere.AsyncClientV2:
    global _client
    if _client is None:
        _client = cohere.AsyncClientV2(api_key=COHERE_API_KEY)
    return _client


async def rerank(query: str, documents: list[str], top_n: int = 5) -> list[int]:
    if not documents:
        return []

    top_n = min(top_n, len(documents))

    try:
        client = _get_client()
        response = await client.rerank(
            model="rerank-v3.5",
            query=query,
            documents=documents,
            top_n=top_n,
        )
        return [result.index for result in response.results]
    except Exception as e:
        logger.warning("Rerank failed, falling back to vector-search order: %r", e)
        return list(range(top_n))
