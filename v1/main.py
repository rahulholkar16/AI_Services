from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
from app.services.llm import create_app_agent
from langgraph.checkpoint.memory import MemorySaver
from app.api.chat import router as ChatRouter
from app.api.repo import router as CloneRouter
from app.api.ask import router as AskRouter
from app.api.analyzer import router as TechStackRouter
from app.api.agent import router as AgentRouter
import app.state as state
import os
import asyncio
import shutil
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

CLONE_DIR = "./cloned_repos"


async def cleanup_old_repos():
    while True:
        try:
            now = datetime.now()
            clone_path = os.path.join(os.getcwd(), CLONE_DIR)
            if os.path.exists(clone_path):
                for owner_dir in os.listdir(clone_path):
                    owner_path = os.path.join(clone_path, owner_dir)
                    for repo_dir in os.listdir(owner_path):
                        repo_path = os.path.join(owner_path, repo_dir)
                        modified_time = datetime.fromtimestamp(os.path.getmtime(repo_path))
                        if datetime.now() - modified_time > timedelta(days=1):
                            shutil.rmtree(repo_path)
                            print(f"🗑️ Deleted: {repo_path}")
                    if os.path.exists(owner_path) and not os.listdir(owner_path):
                        os.rmdir(owner_path)
        except Exception as e:
            print(f"Cleanup error: {e}")
        await asyncio.sleep(6 * 60 * 60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    checkpointer = MemorySaver()
    state.agent = create_app_agent(checkpointer)
    print("Agent ready with Memory!")

    cleanup_task = asyncio.create_task(cleanup_old_repos())

    yield

    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass

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

app.include_router(ChatRouter)
app.include_router(CloneRouter)
app.include_router(AskRouter)
app.include_router(TechStackRouter)
app.include_router(AgentRouter)


@app.get("/")
def main():
    return {"msg": "ok"}


@app.delete("/cleanup/repo")
async def manual_cleanup(repo_url: str):
    try:
        parts = repo_url.rstrip("/").split("github.com/")[-1]
        owner, repo = parts.split("/")[:2]
        repo_path = os.path.join(CLONE_DIR, owner, repo)
        if os.path.exists(repo_path):
            shutil.rmtree(repo_path)
            return {"message": f"Deleted: {repo_path}"}
        return {"message": "Repo not found locally"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))