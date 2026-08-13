# logging setup
from app.config.logging_config import setup_logging
setup_logging()

from fastapi import FastAPI;
from fastapi.middleware.cors import CORSMiddleware;
from contextlib import asynccontextmanager;
from app.config.db import engine;
from app.config.db_graph import init_agent;
from sqlalchemy import text;
from app.middleware.auth import AuthMiddleware
from app.middleware.rate_limit import limiter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import os
import logging
# Routes
from app.api import repo_router, agent_router;

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan (app: FastAPI):
    logger.info("Application is starting...")
    """
    Here we setup DB connetion.
    and Agent Intialization.
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("PostgreSQL connected")
    except Exception as e:
        logger.error("Failed to connect to PostgreSQL: %s", e)
        raise

    async with init_agent():
        yield

    logger.info("Application is stopping")
    await engine.dispose()
    logger.info("PostgreSQL connection pool closed")

app = FastAPI(lifespan=lifespan);

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

FRONTEND_URL = os.getenv("FRONTEND_URL");
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def main ():
    return { "status": "ok" }

app.add_middleware(AuthMiddleware)

app.include_router(repo_router);
app.include_router(agent_router);

