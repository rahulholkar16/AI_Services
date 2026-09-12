import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.tools import create_pull_request_direct
from app.utils.message_store import get_session_id_for_thread, save_message
import app.state as state

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/pr",
    tags=["pr"],
    responses={404: {"description": "Not found"}},
)


class ConfirmRequest(BaseModel):
    thread_id: str
    title: str | None = None
    body: str | None = None


@router.post("/confirm")
async def confirm_pr(body: ConfirmRequest):
    config = {"configurable": {"thread_id": body.thread_id}}

    try:
        current_state = await state.agent.aget_state(config)
    except Exception:
        logger.exception("confirm_pr: failed to read state for thread_id=%s", body.thread_id)
        raise HTTPException(status_code=500, detail="Could not read session state.")

    pr_pending = (current_state.values or {}).get("pr_pending")
    if not pr_pending:
        raise HTTPException(status_code=404, detail="No pending PR proposal found for this thread.")

    result = await create_pull_request_direct(
        repo_full_name=pr_pending["repo_full_name"],
        title=body.title if body.title is not None else pr_pending["title"],
        head=pr_pending["head"],
        base=pr_pending["base"],
        body=body.body if body.body is not None else pr_pending["body"],
    )

    # Clear the pending proposal regardless of outcome — a failed attempt
    # shouldn't be silently retried on the next unrelated message, the user
    # can ask the agent to propose again if they want to retry.
    await state.agent.aupdate_state(config, {"pr_pending": None})

    try:
        session_id = await get_session_id_for_thread(body.thread_id)
        if session_id:
            if "error" in result:
                await save_message(
                    session_id, "tool", f"PR proposal failed: {result['error']}",
                    tool_calls=[{"name": "pr_status", "status": "failed"}],
                )
            else:
                await save_message(
                    session_id, "tool", f"PR created: {result['html_url']}",
                    tool_calls=[{
                        "name": "pr_status",
                        "status": "confirmed",
                        "pr_url": result["html_url"],
                        "pr_number": result["number"],
                    }],
                )
    except Exception:
        logger.exception("confirm_pr: failed to persist resolution for thread_id=%s", body.thread_id)

    if "error" in result:
        return {"success": False, "error": result["error"], "retryable": result.get("retryable", True)}

    return {"success": True, "pr_url": result["html_url"], "pr_number": result["number"]}


@router.post("/reject")
async def reject_pr(body: ConfirmRequest):
    config = {"configurable": {"thread_id": body.thread_id}}

    try:
        await state.agent.aupdate_state(config, {"pr_pending": None})
    except Exception:
        logger.exception("reject_pr: failed to update state for thread_id=%s", body.thread_id)
        raise HTTPException(status_code=500, detail="Could not update session state.")

    try:
        session_id = await get_session_id_for_thread(body.thread_id)
        if session_id:
            await save_message(
                session_id, "tool", "PR proposal cancelled.",
                tool_calls=[{"name": "pr_status", "status": "rejected"}],
            )
    except Exception:
        logger.exception("reject_pr: failed to persist resolution for thread_id=%s", body.thread_id)

    return {"success": True, "message": "PR proposal cancelled."}
