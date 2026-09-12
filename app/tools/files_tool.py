import httpx
import logging
from typing import Annotated
from langchain.tools import tool
from langchain_core.tools import InjectedToolCallId
from langchain_core.messages import ToolMessage
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from app.graph.state import State
import base64
import os
from app.utils import cache_get, cache_set, HEADERS, get_default_branch

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

IGNORE_DIRS = {
    ".git", "node_modules", ".next", "dist",
    "build", "__pycache__", ".venv"
}

ALLOW_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx",
    ".json", ".md", ".yaml", ".yml", ".toml",
    ".css", ".html", ".sh", ".go", ".rs",
    ".java", ".c", ".cpp", ".c++", ".h", ".prisma"
}


@tool
async def list_directory(repo_full_name: str, state: Annotated[State, InjectedState]):
    """
    List ALL files in a GitHub repo recursively.
    Use this first to understand complete project structure.
    repo_full_name format: 'owner/repo'
    """
    try:
        branch = state.get("branch") or await get_default_branch(repo_full_name)
        cache_key = f"tree:{repo_full_name}:{branch}"
        cached = await cache_get(cache_key)
        if cached:
            return cached

        url = f"https://api.github.com/repos/{repo_full_name}/git/trees/{branch}?recursive=1"
        async with httpx.AsyncClient() as client:
            res = await client.get(url, headers=HEADERS)

        if res.status_code >= 400:
            return f"Failed to list repo: {res.status_code}"

        data = res.json()
        tree = data.get("tree", [])
        if not tree:
            return "Empty repository."

        output = []
        for item in tree:
            path = item["path"]

            if any(part in IGNORE_DIRS for part in path.split("/")):
                continue

            if item["type"] == "tree":
                output.append(f"📁 {path}")
            elif item["type"] == "blob":
                ext = "." + path.split(".")[-1].lower() if "." in path else ""
                if ext in ALLOW_EXTENSIONS:
                    output.append(f"📄 {path}")

        total = len(output)
        result = "\n".join(output[:100])
        if not result:
            result = "No relevant files found."
        elif total > 100:
            result += f"\n\n...[truncated: showing 100 of {total} files. Use read_file/search_file for specific paths not shown here.]"

        await cache_set(cache_key, result, ttl=900)
        return result

    except httpx.TimeoutException:
        logger.warning("list_directory timed out for repo=%s", repo_full_name)
        return "Error listing directory: GitHub API timed out. Try again."
    except httpx.RequestError as e:
        logger.warning("list_directory network error for repo=%s: %r", repo_full_name, e)
        return "Error listing directory: network error reaching GitHub."
    except Exception:
        logger.exception("list_directory failed for repo=%s", repo_full_name)
        return "Error listing directory: unexpected error, check server logs."

@tool
async def read_file(repo_full_name: str, file_path: str, state: Annotated[State, InjectedState]):
    """
    Read a specific file from GitHub repo.
    Use for understanding implementation details.
    repo_full_name format: 'owner/repo'
    file_path: 'src/auth.ts', 'app/page.tsx',
    """
    try:
        branch = state.get("branch") or await get_default_branch(repo_full_name)
        cache_key = f"file:{repo_full_name}:{branch}:{file_path}"
        cached = await cache_get(cache_key)
        if cached:
            return cached
        
        url = f"https://api.github.com/repos/{repo_full_name}/contents/{file_path}"
        async with httpx.AsyncClient() as client:
            res = await client.get(url, headers=HEADERS, params={"ref": branch})

        if res.status_code >= 400:
            return f"File not found: {file_path}"

        data = res.json()

        ext = "." + file_path.split(".")[-1].lower() if "." in file_path else ""
        if ext not in ALLOW_EXTENSIONS:
            return f"Binary file skipped: {file_path}"

        content = base64.b64decode(data["content"]).decode("utf-8", errors="ignore")

        if len(content) > 3000:
            content = content[:3000] + "\n...[truncated]"

        result = f"File: {file_path}\n\n{content}"
        await cache_set(cache_key, result, ttl=900)
        return result

    except httpx.TimeoutException:
        logger.warning("read_file timed out for repo=%s path=%s", repo_full_name, file_path)
        return f"Error reading file: GitHub API timed out for {file_path}."
    except httpx.RequestError as e:
        logger.warning("read_file network error for repo=%s path=%s: %r", repo_full_name, file_path, e)
        return f"Error reading file: network error reaching GitHub for {file_path}."
    except Exception:
        logger.exception("read_file failed for repo=%s path=%s", repo_full_name, file_path)
        return f"Error reading file: unexpected error for {file_path}, check server logs."


@tool
async def propose_branch(
    new_branch: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[State, InjectedState],
    source_branch: str | None = None,
) -> Command:
    """
    Propose creating a new branch in the current repo. This does NOT create the branch yet —
    it only stages a proposal and asks the user for confirmation. Use this ONLY when the user
    explicitly asks to create/make a new branch — never assume permission, never call this
    more than once per proposal, and never treat this as if the branch were already created.

    Args:
        new_branch: Name for the new branch (e.g. 'feature/add-caching'). Required — if the
            user hasn't given a name, ask them instead of inventing one.
        source_branch: Branch to create it from. Optional — defaults to the currently active
            branch in this session, or the repo's default branch if none is set.
    """
    repo_full_name = state.get("repo_full_name")
    if not repo_full_name:
        return Command(update={
            "messages": [ToolMessage(
                content="Error: no repo is currently active in this session.",
                tool_call_id=tool_call_id,
            )],
        })

    if not new_branch or not new_branch.strip():
        return Command(update={
            "messages": [ToolMessage(
                content="Error: new_branch name is required. Ask the user what they want to name the branch.",
                tool_call_id=tool_call_id,
            )],
        })

    resolved_source = source_branch or state.get("branch") or await get_default_branch(repo_full_name)

    pending = {
        "repo_full_name": repo_full_name,
        "new_branch": new_branch.strip(),
        "source_branch": resolved_source,
    }

    summary = (
        "I'm ready to create this branch, but I need your confirmation first:\n\n"
        f"- Repo: {repo_full_name}\n"
        f"- New branch: {new_branch.strip()}\n"
        f"- From: {resolved_source}\n\n"
        "Reply 'confirm' / 'yes' to create it, tell me a different name/source branch, "
        "or say 'cancel' to drop this."
    )

    return Command(update={
        "branch_pending": pending,
        "messages": [ToolMessage(content=summary, tool_call_id=tool_call_id)],
    })


@tool
async def search_file(query: str, state: Annotated[State, InjectedState]) -> str:
    """
    Search files by name in GitHub repo.
    """
    try:
        repo_full_name = state["repo_full_name"]
        cache_key = f"search_file:{repo_full_name}:{query}"
        cached = await cache_get(cache_key)
        if cached:
            return cached

        url = "https://api.github.com/search/code"
        params = {"q": f"repo:{repo_full_name} filename:{query}", "per_page": 10}
        async with httpx.AsyncClient() as client:
            res = await client.get(url, headers=HEADERS, params=params)

        if res.status_code >= 400:
            return f"Search failed: {res.status_code}"

        items = res.json().get("items", [])
        if not items:
            return f"No files found for: {query}"

        result = "\n".join([f"📄 {item['path']}" for item in items])
        await cache_set(cache_key, result, ttl=900)
        return result

    except httpx.TimeoutException:
        logger.warning("search_file timed out for query=%s", query)
        return "Error searching file: GitHub API timed out. Try again."
    except httpx.RequestError as e:
        logger.warning("search_file network error for query=%s: %r", query, e)
        return "Error searching file: network error reaching GitHub."
    except Exception:
        logger.exception("search_file failed for query=%s", query)
        return "Error searching file: unexpected error, check server logs."


@tool
async def search_code(query: str, state: Annotated[State, InjectedState]) -> str:
    """
    Search for exact keyword inside code files.
    Use this for exact string/symbol matches (e.g. a specific function
    or variable name). For conceptual/semantic questions, prefer
    search_codebase instead.
    """
    try:
        repo_full_name = state["repo_full_name"]
        cache_key = f"search_code:{repo_full_name}:{query}"
        cached = await cache_get(cache_key)
        if cached:
            return cached

        url = "https://api.github.com/search/code"
        params = {"q": f"repo:{repo_full_name} {query}", "per_page": 10}
        async with httpx.AsyncClient() as client:
            res = await client.get(url, headers=HEADERS, params=params)

        if res.status_code >= 400:
            return f"Search failed: {res.status_code}"

        items = res.json().get("items", [])
        if not items:
            return f"No code found for: {query}"

        result = "\n".join([f"📄 {item['path']}" for item in items])
        await cache_set(cache_key, result, ttl=900)
        return result

    except httpx.TimeoutException:
        logger.warning("search_code timed out for query=%s", query)
        return "Error searching code: GitHub API timed out. Try again."
    except httpx.RequestError as e:
        logger.warning("search_code network error for query=%s: %r", query, e)
        return "Error searching code: network error reaching GitHub."
    except Exception:
        logger.exception("search_code failed for query=%s", query)
        return "Error searching code: unexpected error, check server logs."
