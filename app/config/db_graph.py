import os;
import logging;
from contextlib import asynccontextmanager;
from psycopg_pool import AsyncConnectionPool;
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver;
from app.graph import build_graph;
from .db_store import init_store;
import app.state as state

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("CHECKPOINT_DATABASE_URL", "")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1);


connection_kwargs = {
    "autocommit": True,
    "prepare_threshold": 0,
}

@asynccontextmanager
async def init_agent():
    # In production with multiple replicas, run `python -m scripts.migrate`
    # once (before any instance starts) and set AUTO_MIGRATE_ON_STARTUP=false
    # here, so instances don't race to CREATE TABLE concurrently on boot.
    # Defaults to true for local/single-instance dev convenience.
    auto_migrate = os.getenv("AUTO_MIGRATE_ON_STARTUP", "true").lower() == "true"

    async with AsyncConnectionPool(
        conninfo=DATABASE_URL,
        max_size=40,
        min_size=5,
        max_lifetime=1800,
        max_idle=600,
        reconnect_timeout=10,
        kwargs=connection_kwargs,
        check=AsyncConnectionPool.check_connection,
    ) as pool:
        
        checkpointer = AsyncPostgresSaver(pool)
        if auto_migrate:
            await checkpointer.setup();

        store = await init_store(pool);
        if auto_migrate:
            await store.setup();
        state.store = store;

        state.agent = await build_graph(checkpointer, store);
        logger.info("Agent ready with Postgres memory (pooled)")
        yield
    logger.info("Agent connection closed")