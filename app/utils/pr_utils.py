import logging
import httpx
from app.utils.github_helpers import HEADERS, friendly_pr_error

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
            body_json = res.json() if res.content else {}
            detail = body_json.get("message", res.text)
            errors = body_json.get("errors") or []
            logger.warning(
                "create_pull_request_direct failed: %s - %s | errors=%s | payload=%s",
                res.status_code, detail, errors, payload,
            )
            friendly = friendly_pr_error(res.status_code, detail, errors, head, base)
            return {"error": friendly["message"], "retryable": friendly["retryable"]}

        data = res.json()
        return {"html_url": data["html_url"], "number": data["number"]}

    except httpx.TimeoutException:
        logger.warning("create_pull_request_direct timed out for repo=%s", repo_full_name)
        return {"error": "GitHub API timed out while creating the PR.", "retryable": True}
    except httpx.RequestError as e:
        logger.warning("create_pull_request_direct network error for repo=%s: %r", repo_full_name, e)
        return {"error": "Network error reaching GitHub while creating the PR.", "retryable": True}
    except Exception:
        logger.exception("create_pull_request_direct failed for repo=%s", repo_full_name)
        return {"error": "Unexpected error creating the PR, check server logs.", "retryable": True}
