from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
from app.services.llm import create_app_agent
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
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

DATABASE_URL = os.getenv("DATABASE_URL", "")
CLONE_DIR = "./cloned_repos"  # Jahan repos clone hote hain

# ✅ postgres:// → postgresql:// fix
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)


async def cleanup_old_repos():
    """
    Cloned repos jo 1 din se purane hain unhe delete karo.
    Har 6 ghante mein run hoga.
    """
    while True:
        try:
            now = datetime.now()
            clone_path = os.path.join(os.getcwd(), CLONE_DIR)

            if os.path.exists(clone_path):
                for owner_dir in os.listdir(clone_path):
                    owner_path = os.path.join(clone_path, owner_dir)

                    for repo_dir in os.listdir(owner_path):
                        repo_path = os.path.join(owner_path, repo_dir)

                        # Last modified time check karo
                        modified_time = datetime.fromtimestamp(
                            os.path.getmtime(repo_path)
                        )
                        age = now - modified_time

                        # 1 din se purana hai toh delete karo
                        if age > timedelta(days=1):
                            shutil.rmtree(repo_path)
                            print(f"🗑️ Deleted old repo: {repo_path}")

                    # Owner dir empty hai toh wo bhi delete karo
                    if os.path.exists(owner_path) and not os.listdir(owner_path):
                        os.rmdir(owner_path)

        except Exception as e:
            print(f"Cleanup error: {e}")

        # Har 6 ghante mein run karo
        await asyncio.sleep(6 * 60 * 60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncPostgresSaver.from_conn_string(
        DATABASE_URL,
    ) as checkpointer:
        await checkpointer.setup()
        state.agent = create_app_agent(checkpointer)
        print("Agent ready with Postgres memory!")

        # ✅ Cleanup task background mein start karo
        cleanup_task = asyncio.create_task(cleanup_old_repos())
        print("Cleanup task started!")

        yield

        # ✅ App band hone pe cleanup task cancel karo
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            print("Cleanup task stopped.")

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


# ✅ Manual delete endpoint bhi add kiya
@app.delete("/cleanup/repo")
async def manual_cleanup(repo_url: str):
    """Manually ek specific repo delete karo."""
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