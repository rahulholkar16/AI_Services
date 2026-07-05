from fastapi import FastAPI;
from fastapi.middleware.cors import CORSMiddleware;
from contextlib import asynccontextmanager;
from app.config.db import engine;
from app.config.db_graph import init_agent;
from sqlalchemy import text;
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver;
# Routes
from app.api import repo_router, agent_router;

@asynccontextmanager
async def lifespan (app: FastAPI):
    print("Application is Start>>>");
    """
    Here we setup DB connetion.
    and Agent Intialization.
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        print("✅ PostgreSQL Connected")
    except Exception as e:
        print(f"❌ Failed to connect to PostgreSQL: {e}")
        raise

    async with init_agent():
        yield

    print("Application is Stopped")
    await engine.dispose()
    print("PostgreSQL Connection Pool Closed")

app = FastAPI(lifespan=lifespan);

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(repo_router);
app.include_router(agent_router);

@app.get("/")
def main ():
    return { "status": "ok" }