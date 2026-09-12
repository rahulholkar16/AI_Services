import logging
from app.utils.github_helpers import HEADERS
import httpx

logger = logging.getLogger(__name__)
GITHUB_API = "https://api.github.com"


async def create_branch_direct(
    repo_full_name: str,
    new_branch: str,
    source_branch: str,
) -> dict:
    """
    Actually creates the branch on GitHub. Called only from the /api/branch/confirm
    route after the user has explicitly confirmed a pending proposal —
    never called directly by the LLM/agent.
    """
    try:
        async with httpx.AsyncClient() as client:
            ref_res = await client.get(
                f"{GITHUB_API}/repos/{repo_full_name}/git/ref/heads/{source_branch}",
                headers=HEADERS,
            )

            if ref_res.status_code >= 400:
                return {"error": f"Couldn't find source branch '{source_branch}' to branch from (status {ref_res.status_code}).", "retryable": False}

            sha = ref_res.json().get("object", {}).get("sha")
            if not sha:
                return {"error": f"Couldn't resolve the latest commit for branch '{source_branch}'.", "retryable": False}

            create_res = await client.post(
                f"{GITHUB_API}/repos/{repo_full_name}/git/refs",
                headers=HEADERS,
                json={"ref": f"refs/heads/{new_branch}", "sha": sha},
            )

        if create_res.status_code >= 400:
            body_json = create_res.json() if create_res.content else {}
            detail = body_json.get("message", create_res.text)
            logger.warning("create_branch_direct failed: %s - %s", create_res.status_code, detail)
            if "already exists" in detail.lower():
                return {"error": f"Branch '{new_branch}' already exists in {repo_full_name}.", "retryable": False}
            return {"error": f"GitHub couldn't create the branch: {detail}", "retryable": True}

        return {
            "branch": new_branch,
            "source_branch": source_branch,
            "html_url": f"https://github.com/{repo_full_name}/tree/{new_branch}",
        }

    except httpx.TimeoutException:
        logger.warning("create_branch_direct timed out for repo=%s", repo_full_name)
        return {"error": "GitHub API timed out while creating the branch.", "retryable": True}
    except httpx.RequestError as e:
        logger.warning("create_branch_direct network error for repo=%s: %r", repo_full_name, e)
        return {"error": "Network error reaching GitHub while creating the branch.", "retryable": True}
    except Exception:
        logger.exception("create_branch_direct failed for repo=%s", repo_full_name)
        return {"error": "Unexpected error creating the branch, check server logs.", "retryable": True}
