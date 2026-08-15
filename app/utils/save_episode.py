import logging
import uuid
import asyncio
from .episodic_extractor import _extract_episode
from .task_utils import log_task_exception

logger = logging.getLogger(__name__)

MAX_EPISODES_PER_REPO = 100

def _memory_namespace(repo_id: str, user_id: str, kind: str) -> tuple:
    return ("repo", repo_id, "user", user_id, kind)


async def _save_episode(question, answer, repo_id, user_id, store):
    try:
        result = await _extract_episode(question, answer)
        if not result:
            return

        namespace = _memory_namespace(repo_id, user_id, "episodes")
        await store.aput(
            namespace,
            str(uuid.uuid4()),
            {
                "content": result.content,
                "topic": result.topic,
                "importance": result.importance,
            },
        )

        prune_task = asyncio.create_task(_prune_episodes(namespace, store))
        prune_task.add_done_callback(log_task_exception)

    except Exception as e:
        logger.warning("Episode extraction/save failed: %r", e)


async def _prune_episodes(namespace: tuple, store, max_episodes: int = MAX_EPISODES_PER_REPO) -> None:
    all_episodes = await store.asearch(namespace, limit=max_episodes + 50)
    if len(all_episodes) <= max_episodes:
        return

    sorted_episodes = sorted(
        all_episodes,
        key=lambda e: (e.value.get("importance", 3), e.created_at),
    )

    to_delete = sorted_episodes[: len(all_episodes) - max_episodes]
    for ep in to_delete:
        await store.adelete(namespace, ep.key)

    logger.info(
        "Pruned %d episode(s) from %s (kept %d most important/recent)",
        len(to_delete), namespace, max_episodes,
    )
