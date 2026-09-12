import os
import logging
import httpx
from dotenv import load_dotenv
from app.utils.redis_util import cache_get, cache_set

load_dotenv()

logger = logging.getLogger(__name__)

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {
    "Accept": "application/vnd.github+json"
}

if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"Bearer {GITHUB_TOKEN}"


async def get_default_branch(repo_full_name: str) -> str:
    """Repo ka default branch (main/master) pata karo."""
    key = f"default_branch:{repo_full_name}"
    cached = await cache_get(key)
    if cached:
        return cached

    url = f"https://api.github.com/repos/{repo_full_name}"
    async with httpx.AsyncClient() as client:
        res = await client.get(url, headers=HEADERS)
    if res.status_code < 400:
        branch = res.json().get("default_branch", "main")
        await cache_set(key, branch, ttl=3600)
        return branch

    return "main"


def friendly_pr_error(status_code: int, detail: str, errors: list, head: str, base: str) -> dict:
    """Turn GitHub's raw 422 payload into a message a non-technical user can act on.
    Returns {"message": str, "retryable": bool} — retryable=False means editing
    title/description and hitting Confirm again won't help (e.g. branch not pushed yet).
    """
    messages = " ".join(str(e.get("message", "")) for e in errors if isinstance(e, dict))
    text = f"{detail} {messages}".lower()

    if "already exists" in text:
        return {
            "message": f"A pull request from '{head}' into '{base}' is already open. "
                       "Close or merge it before opening a new one, or ask to update the existing PR instead.",
            "retryable": False,
        }
    if "no commits between" in text:
        return {
            "message": f"'{head}' has no new commits compared to '{base}'. "
                       "Make sure your changes are pushed to GitHub, then try again.",
            "retryable": False,
        }
    if "not found" in text or status_code == 404:
        return {
            "message": f"Couldn't find branch '{head}' or '{base}' on GitHub. "
                       "Double-check the branch names and that they've been pushed.",
            "retryable": False,
        }
    return {"message": f"GitHub couldn't create the PR: {detail}", "retryable": True}
