from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel;
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage;
import asyncio;
from app.utils.Repo_Full_Name_Extracter import extract_full_name;
from app.utils.message_store import get_or_create_session_id, save_message, generate_and_save_title;
import app.state as state

class AgentRequest(BaseModel):
    repo_url:  str
    question:  str
    thread_id: str
    repo_id:   str

router = APIRouter();

def extract_text(content):
    # Groq/OpenAI
    if isinstance(content, str):
        return content
    
    # Gemini
    if isinstance(content, list):
        text_parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block["text"])
            elif isinstance(block, str):
                text_parts.append(block)
        return "\n".join(text_parts)
    
    return str(content)

@router.post("/agent/chat")
async def agent_chat(request: AgentRequest):

    async def event_generator ():
        session_id = None
        assistant_text_parts = []

        try:
            repo_full_name = extract_full_name(request.repo_url)

            config = {"configurable": {"thread_id": request.thread_id}}
            print("Thread ID:: ", request.thread_id);

            session_id = await get_or_create_session_id(request.thread_id, request.repo_id, request.question)
            if session_id:
                await save_message(session_id, "user", request.question)
                asyncio.create_task(generate_and_save_title(session_id, request.question))

            async for chunk in state.agent.astream(
                {
                    "messages": [HumanMessage(content=request.question)],
                    "repo_url": request.repo_url,
                    "repo_full_name": repo_full_name,
                    "repo_id": request.repo_id,
                    "thread_id": request.thread_id,
                    "pr_pending": None,
                },
                config=config
            ):
                    for _, node_data in chunk.items():
                        if not node_data:
                            continue

                        messages = node_data.get("messages")
                        if not messages:
                            continue

                        for msg in messages:

                            if isinstance(msg, ToolMessage):
                                print("\nTOOL_RESULT:: ", msg.name)
                                if session_id:
                                    await save_message(
                                        session_id,
                                        "tool",
                                        extract_text(msg.content) or (msg.name or "tool"),
                                        tool_calls=[{"name": msg.name, "type": "tool_result"}],
                                    )
                                yield {
                                    "event": "tool_result",
                                    "data": msg.name or "tool",
                                }
                                continue

                            if isinstance(msg, AIMessage) and msg.tool_calls:
                                for tc in msg.tool_calls:
                                    print("\nTOOL_CALL:: ", tc["name"])
                                    if session_id:
                                        await save_message(
                                            session_id,
                                            "tool",
                                            tc["name"],
                                            tool_calls=[{"name": tc["name"], "args": tc.get("args"), "type": "tool_call"}],
                                        )
                                    yield {
                                        "event": "tool_call",
                                        "data": tc["name"],
                                    }
                                continue
                            text = extract_text(msg.content)
                            print("\nCHUNK:: ", text)
                            if text:
                                assistant_text_parts.append(text)
                                yield {
                                    "event": "message",
                                    "data": text,
                                }

            if session_id and assistant_text_parts:
                await save_message(session_id, "assistant", "\n".join(assistant_text_parts))

            yield {
                "event": "done",
                "data": "completed",
            }

        except Exception as e:
            if session_id and assistant_text_parts:
                await save_message(session_id, "assistant", "\n".join(assistant_text_parts))
            yield ServerSentEvent(
                event="error",
                data=str(e)
            )
        
    return EventSourceResponse(
        event_generator(),
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )