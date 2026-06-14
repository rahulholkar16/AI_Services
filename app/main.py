from fastapi import FastAPI;
from contextlib import asynccontextmanager;
from app.services.llm import create_app_agent
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from app.api.chat import router as ChatRouter;
from app.api.repo import router as CloneRouter;
from app.api.ask import router as AskRouter;
from app.api.analyzer import router as TechStackRouter;
from app.api.agent import router as AgentRouter;
import app.state as state
import os
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncPostgresSaver.from_conn_string(
        DATABASE_URL
    ) as checkpointer:

        await checkpointer.setup()

        state.agent = create_app_agent(checkpointer)

        print("Agent ready with Postgres memory!")

        yield

    print("Agent shutting down...")
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ChatRouter);
app.include_router(CloneRouter);
app.include_router(AskRouter);
app.include_router(TechStackRouter);
app.include_router(AgentRouter);

@app.get("/")
def main ():
    return { "msg": "ok" }