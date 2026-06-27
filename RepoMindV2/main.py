from fastapi import FastAPI;
from fastapi.middleware.cors import CORSMiddleware;
from contextlib import asynccontextmanager;
from config.db import engine;

@asynccontextmanager
async def lifespan (app: FastAPI):
    print("Application is Start>>>");
    """
    Here we setup DB connetion.
    and Agent Intialization.
    """
    try:
        async with engine.connect() as conn:
            await conn.execute("SELECT 1")
        print("✅ PostgreSQL Connected")
    except Exception as e:
        print(f"❌ Failed to connect to PostgreSQL: {e}")
        raise

    yield
    print("Application is Stoped");
    """
        We close the DB connection and Agent and Other temp memory.
    """

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

@app.get("/")
def main ():
    return { "status": "ok" }