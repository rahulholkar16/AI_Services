import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.tools import create_branch_direct
from app.utils.message_store import get_session_id_for_thread, save_message
import app.state as state

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/branch",
    tags=["branch"],
    responses={404: {"description": "Not found"}},
)


class ConfirmRequest(BaseModel):
    thread_id: str
    new_branch: str | None = None
    source_branch: str | None = None


@router.post("/confirm")
async def confirm_branch(body: ConfirmRequest):
    config = {"configurable": {"thread_id": body.thread_id}}

    try:
        current_state = await state.agent.aget_state(config)
    except Exception:
        logger.exception("confirm_branch: failed to read state for thread_id=%s", body.thread_id)
        raise HTTPException(status_code=500, detail="Could not read session state.")

    branch_pending = (current_state.values or {}).get("branch_pending")
    if not branch_pending:
        raise HTTPException(status_code=404, detail="No pending branch proposal found for this thread.")

    result = await create_branch_direct(
        repo_full_name=branch_pending["repo_full_name"],
        new_branch=body.new_branch if body.new_branch is not None else branch_pending["new_branch"],
        source_branch=body.source_branch if body.source_branch is not None else branch_pending["source_branch"],
    )

    await state.agent.aupdate_state(config, {"branch_pending": None})

    try:
        session_id = await get_session_id_for_thread(body.thread_id)
        if session_id:
            if "error" in result:
                await save_message(
                    session_id, "tool", f"Branch proposal failed: {result['error']}",
                    tool_calls=[{"name": "branch_status", "status": "failed"}],
                )
            else:
                await save_message(
                    session_id, "tool", f"Branch created: {result['html_url']}",
                    tool_calls=[{
                        "name": "branch_status",
                        "status": "confirmed",
                        "branch": result["branch"],
                        "source_branch": result["source_branch"],
                        "branch_url": result["html_url"],
                    }],
                )
    except Exception:
        logger.exception("confirm_branch: failed to persist resolution for thread_id=%s", body.thread_id)

    if "error" in result:
        return {"success": False, "error": result["error"], "retryable": result.get("retryable", True)}

    return {"success": True, "branch": result["branch"], "branch_url": result["html_url"]}


@router.post("/reject")
async def reject_branch(body: ConfirmRequest):
    config = {"configurable": {"thread_id": body.thread_id}}

    try:
        await state.agent.aupdate_state(config, {"branch_pending": None})
    except Exception:
        logger.exception("reject_branch: failed to update state for thread_id=%s", body.thread_id)
        raise HTTPException(status_code=500, detail="Could not update session state.")

    try:
        session_id = await get_session_id_for_thread(body.thread_id)
        if session_id:
            await save_message(
                session_id, "tool", "Branch proposal cancelled.",
                tool_calls=[{"name": "branch_status", "status": "rejected"}],
            )
    except Exception:
        logger.exception("reject_branch: failed to persist resolution for thread_id=%s", body.thread_id)

    return {"success": True, "message": "Branch proposal cancelled."}
