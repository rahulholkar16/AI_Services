import logging
from typing import Annotated
import httpx
from langchain.tools import tool
from langchain_core.tools import InjectedToolCallId
from langchain_core.messages import ToolMessage
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from app.graph.state import State
from app.tools.files_tool import HEADERS, get_default_branch
from app.utils import cache_get, cache_set

logger = logging.getLogger(__name__)
GITHUB_API = "https://api.github.com"


@tool
async def fetch_all_pull_request(
    state: Annotated[State, InjectedState],
    pr_state: str = "open",
) -> str:
    """
    List pull requests for the current repo.

    Args:
        pr_state: One of 'open', 'closed', or 'all'. Optional, defaults to 'open'.
            Only pass this if the user specifically asks for closed/all PRs.
    """
    repo_full_name = state.get("repo_full_name")
    if not repo_full_name:
        return "Error: no repo is currently active in this session. Ask the user to select a repo first."

    if pr_state not in ("open", "closed", "all"):
        pr_state = "open"

    try:
        cache_key = f"pr_list:{repo_full_name}:{pr_state}"
        cached = await cache_get(cache_key)
        if cached:
            return cached

        url = f"{GITHUB_API}/repos/{repo_full_name}/pulls"
        async with httpx.AsyncClient() as client:
            res = await client.get(url, headers=HEADERS, params={"state": pr_state, "per_page": 20})

        if res.status_code >= 400:
            return f"Failed to list PRs: {res.status_code}"

        prs = res.json()
        if not prs:
            return f"No {pr_state} pull requests found."

        lines = []
        for pr in prs:
            lines.append(
                f"#{pr['number']} [{pr['state']}] {pr['title']} "
                f"({pr['head']['ref']} -> {pr['base']['ref']}) by {pr['user']['login']} "
                f"- {pr['html_url']}"
            )
        result = "\n".join(lines)
        await cache_set(cache_key, result, ttl=120)
        return result

    except httpx.TimeoutException:
        logger.warning("fetch_all_pull_request timed out for repo=%s", repo_full_name)
        return "Error listing PRs: GitHub API timed out. Try again."
    except httpx.RequestError as e:
        logger.warning("fetch_all_pull_request network error for repo=%s: %r", repo_full_name, e)
        return "Error listing PRs: network error reaching GitHub."
    except Exception:
        logger.exception("fetch_all_pull_request failed for repo=%s", repo_full_name)
        return "Error listing PRs: unexpected error, check server logs."


@tool
async def get_pr_status(
    pr_number: int,
    state: Annotated[State, InjectedState],
) -> str:
    """
    Get detailed status of a single pull request in the current repo: mergeable state,
    checks, commits, changed files. Use this to check if a PR is ready to merge or has conflicts.

    Args:
        pr_number: The pull request number, as an integer (e.g. 42). Required.
            If the user hasn't given a PR number, ask them for it instead of guessing.
    """
    repo_full_name = state.get("repo_full_name")
    if not repo_full_name:
        return "Error: no repo is currently active in this session. Ask the user to select a repo first."

    if not pr_number or not isinstance(pr_number, int):
        return "Error: pr_number is required and must be an integer. Ask the user which PR number they mean."

    try:
        cache_key = f"pr_status:{repo_full_name}:{pr_number}"
        cached = await cache_get(cache_key)
        if cached:
            return cached

        url = f"{GITHUB_API}/repos/{repo_full_name}/pulls/{pr_number}"
        async with httpx.AsyncClient() as client:
            res = await client.get(url, headers=HEADERS)

        if res.status_code >= 400:
            return f"PR #{pr_number} not found: {res.status_code}"

        data = res.json()
        result = (
            f"PR #{pr_number}: {data['title']}\n"
            f"State: {data['state']} | Draft: {data.get('draft', False)}\n"
            f"Mergeable: {data.get('mergeable')} | Mergeable state: {data.get('mergeable_state')}\n"
            f"Branch: {data['head']['ref']} -> {data['base']['ref']}\n"
            f"Commits: {data.get('commits')} | Changed files: {data.get('changed_files')} "
            f"| +{data.get('additions')} -{data.get('deletions')}\n"
            f"Author: {data['user']['login']}\n"
            f"URL: {data['html_url']}"
        )
        await cache_set(cache_key, result, ttl=60)
        return result

    except httpx.TimeoutException:
        logger.warning("get_pr_status timed out for repo=%s pr=%s", repo_full_name, pr_number)
        return "Error fetching PR status: GitHub API timed out."
    except httpx.RequestError as e:
        logger.warning("get_pr_status network error for repo=%s pr=%s: %r", repo_full_name, pr_number, e)
        return "Error fetching PR status: network error reaching GitHub."
    except Exception:
        logger.exception("get_pr_status failed for repo=%s pr=%s", repo_full_name, pr_number)
        return "Error fetching PR status: unexpected error, check server logs."


@tool
async def get_pr_diff(
    pr_number: int,
    state: Annotated[State, InjectedState],
) -> str:
    """
    Get the code diff/changes of a pull request in the current repo, for review or analysis.
    Use this before answering questions about what a PR changes, whether it looks safe,
    or to summarize/review its contents.

    Args:
        pr_number: The pull request number, as an integer (e.g. 42). Required.
            If the user hasn't given a PR number, ask them for it instead of guessing.
    """
    repo_full_name = state.get("repo_full_name")
    if not repo_full_name:
        return "Error: no repo is currently active in this session. Ask the user to select a repo first."

    if not pr_number or not isinstance(pr_number, int):
        return "Error: pr_number is required and must be an integer. Ask the user which PR number they mean."

    try:
        cache_key = f"pr_diff:{repo_full_name}:{pr_number}"
        cached = await cache_get(cache_key)
        if cached:
            return cached

        url = f"{GITHUB_API}/repos/{repo_full_name}/pulls/{pr_number}"
        diff_headers = {**HEADERS, "Accept": "application/vnd.github.v3.diff"}
        async with httpx.AsyncClient() as client:
            res = await client.get(url, headers=diff_headers)

        if res.status_code >= 400:
            return f"Failed to fetch diff for PR #{pr_number}: {res.status_code}"

        diff = res.text
        if not diff.strip():
            return f"PR #{pr_number} has no diff (empty or binary-only changes)."

        if len(diff) > 8000:
            diff = diff[:8000] + "\n...[diff truncated, too large to show in full]"

        result = f"Diff for PR #{pr_number}:\n\n{diff}"
        await cache_set(cache_key, result, ttl=120)
        return result

    except httpx.TimeoutException:
        logger.warning("get_pr_diff timed out for repo=%s pr=%s", repo_full_name, pr_number)
        return "Error fetching PR diff: GitHub API timed out."
    except httpx.RequestError as e:
        logger.warning("get_pr_diff network error for repo=%s pr=%s: %r", repo_full_name, pr_number, e)
        return "Error fetching PR diff: network error reaching GitHub."
    except Exception:
        logger.exception("get_pr_diff failed for repo=%s pr=%s", repo_full_name, pr_number)
        return "Error fetching PR diff: unexpected error, check server logs."


@tool
async def propose_pull_request(
    title: str,
    description: str,
    head_branch: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[State, InjectedState],
    base_branch: str | None = None,
) -> Command:
    """
    Propose creating a pull request in the current repo. This does NOT create the PR yet —
    it only stages a proposal and asks the user for confirmation. ALWAYS use this tool whenever
    the user asks to open/create a PR — never assume permission, never call this more than once
    per proposal, and never treat this as if the PR were already created.

    Args:
        title: A clear, descriptive PR title. Required — you must come up with this yourself
            based on the branch name and/or diff/context available in the conversation.
        description: A short description of what the PR changes. Required — write this yourself,
            don't leave it empty.
        head_branch: The branch with the changes (source), as a string. Required — if the user
            hasn't specified it, ask them instead of guessing.
        base_branch: The branch to merge into (target). Optional — defaults to the repo's
            default branch if not given.
    """
    repo_full_name = state.get("repo_full_name")
    if not repo_full_name:
        return Command(update={
            "messages": [ToolMessage(
                content="Error: no repo is currently active in this session.",
                tool_call_id=tool_call_id,
            )],
        })

    missing = [name for name, val in [("title", title), ("description", description), ("head_branch", head_branch)] if not val]
    if missing:
        return Command(update={
            "messages": [ToolMessage(
                content=f"Error: missing required field(s) {', '.join(missing)}. "
                        "Ask the user for these before proposing the PR.",
                tool_call_id=tool_call_id,
            )],
        })

    resolved_base = base_branch or state.get("branch") or await get_default_branch(repo_full_name)

    pending = {
        "repo_full_name": repo_full_name,
        "title": title,
        "body": description,
        "head": head_branch,
        "base": resolved_base,
    }

    summary = (
        "I'm ready to open this pull request, but I need your confirmation first:\n\n"
        f"- Repo: {repo_full_name}\n"
        f"- Title: {title}\n"
        f"- Description: {description}\n"
        f"- Branch: {head_branch} -> {resolved_base}\n\n"
        "Reply 'confirm' / 'yes' to create it, tell me what to change (title/description/branch), "
        "or say 'cancel' to drop this."
    )

    return Command(update={
        "pr_pending": pending,
        "messages": [ToolMessage(content=summary, tool_call_id=tool_call_id)],
    })


async def create_pull_request_direct(
    repo_full_name: str,
    title: str,
    head: str,
    base: str,
    body: str,
) -> dict:
    """
    Actually creates the PR on GitHub. Called only from the /api/pr/confirm
    route after the user has explicitly confirmed a pending proposal —
    never called directly by the LLM/agent.
    """
    url = f"{GITHUB_API}/repos/{repo_full_name}/pulls"
    payload = {"title": title, "head": head, "base": base, "body": body}

    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(url, headers=HEADERS, json=payload)

        if res.status_code >= 400:
            detail = res.json().get("message", res.text) if res.content else res.text
            logger.warning("create_pull_request_direct failed: %s - %s", res.status_code, detail)
            return {"error": f"GitHub rejected the PR ({res.status_code}): {detail}"}

        data = res.json()
        return {"html_url": data["html_url"], "number": data["number"]}

    except httpx.TimeoutException:
        logger.warning("create_pull_request_direct timed out for repo=%s", repo_full_name)
        return {"error": "GitHub API timed out while creating the PR."}
    except httpx.RequestError as e:
        logger.warning("create_pull_request_direct network error for repo=%s: %r", repo_full_name, e)
        return {"error": "Network error reaching GitHub while creating the PR."}
    except Exception:
        logger.exception("create_pull_request_direct failed for repo=%s", repo_full_name)
        return {"error": "Unexpected error creating the PR, check server logs."}
