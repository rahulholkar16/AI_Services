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
    async with AsyncConnectionPool(
        conninfo=DATABASE_URL,
        max_size=10,
        min_size=1,
        kwargs=connection_kwargs,
        check=AsyncConnectionPool.check_connection,
    ) as pool:
        
        checkpointer = AsyncPostgresSaver(pool)
        await checkpointer.setup();

        store = await init_store(pool);
        await store.setup();
        state.store = store;

        state.agent = await build_graph(checkpointer, store);
        logger.info("Agent ready with Postgres memory (pooled)")
        yield
    logger.info("Agent connection closed")