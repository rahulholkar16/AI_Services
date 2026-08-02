import os;
from contextlib import asynccontextmanager;
from psycopg_pool import AsyncConnectionPool;
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver;
from app.graph import build_graph;
import app.state as state

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
        kwargs=connection_kwargs,
    ) as pool:
        checkpointer = AsyncPostgresSaver(pool)
        await checkpointer.setup();
        state.agent = await build_graph(checkpointer);
        print("✅ Agent ready with Postgres memory (pooled)!");
        yield
    print("Agent connection closed.");