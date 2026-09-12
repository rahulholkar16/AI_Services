import logging
import httpx
from app.tools.files_tool import HEADERS

logger = logging.getLogger(__name__)
GITHUB_API = "https://api.github.com"


async def create_pull_request_direct(
    repo_full_name: str,
    title: str,
    head: str,
    base: str,
    body: str = "",
) -> dict:
    """
    Actually create the pull request on GitHub. This is NOT an agent tool — the LLM
    can never call this directly. It is only called from backend code (e.g. agent.py)
    after the user has explicitly confirmed a pending proposal created by
    propose_pull_request.

    Returns a dict with either the created PR info (number, html_url, title, state)
    or an 'error' key describing what went wrong.
    """
    url = f"{GITHUB_API}/repos/{repo_full_name}/pulls"
    payload = {"title": title, "head": head, "base": base, "body": body}

    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(url, headers=HEADERS, json=payload)

        if res.status_code >= 400:
            try:
                detail = res.json().get("message", res.text)
            except Exception:
                detail = res.text
            logger.warning(
                "create_pull_request_direct failed for repo=%s: %s - %s",
                repo_full_name, res.status_code, detail,
            )
            return {"error": f"Failed to create PR: {detail}"}

        data = res.json()
        return {
            "number": data["number"],
            "html_url": data["html_url"],
            "title": data["title"],
            "state": data["state"],
        }

    except httpx.TimeoutException:
        logger.warning("create_pull_request_direct timed out for repo=%s", repo_full_name)
        return {"error": "GitHub API timed out while creating PR."}
    except httpx.RequestError as e:
        logger.warning("create_pull_request_direct network error for repo=%s: %r", repo_full_name, e)
        return {"error": "Network error reaching GitHub while creating PR."}
    except Exception:
        logger.exception("create_pull_request_direct failed for repo=%s", repo_full_name)
        return {"error": "Unexpected error creating PR, check server logs."}
