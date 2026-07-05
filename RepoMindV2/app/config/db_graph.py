import os;
from contextlib import asynccontextmanager;
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver;
from app.graph import build_graph;
import app.state as state

DATABASE_URL = os.getenv("DATABASE_URL", "")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1);

@asynccontextmanager
async def init_agent():
    async with AsyncPostgresSaver.from_conn_string(DATABASE_URL) as checkpointer:
        await checkpointer.setup();
        state.agent = await build_graph(checkpointer);
        print("✅ Agent ready with Postgres memory!");
        yield
    print("Agent connection closed.");