import logging
from .fact_extractor import _extract_fact

logger = logging.getLogger(__name__)

def _memory_namespace(repo_id: str, user_id: str, kind: str) -> tuple:
    return ("repo", repo_id, "user", user_id, kind)

async def _save_fact(question, answer, repo_id, user_id, store):
    try:
        result = await _extract_fact(question, answer)
        if result:
            topic, fact = result
            await store.aput(
                _memory_namespace(repo_id, user_id, "facts"),
                topic,
                {"content": fact},
            )
    except Exception as e:
            logger.warning("Fact extraction/save failed: %r", e)
