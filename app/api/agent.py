from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel;
from langchain_core.messages import HumanMessage;
from app.utils.Repo_Full_Name_Extracter import extract_full_name;
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
        try:
            repo_full_name = extract_full_name(request.repo_url)

            config = {"configurable": {"thread_id": request.thread_id}}
            print("Thread ID:: ", request.thread_id);

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
                    print("\nCHUNK:: ", chunk)
                    for _, node_data in chunk.items():
                        if not node_data:
                            continue

                        messages = node_data.get("messages")
                        if not messages:
                            continue

                        last_message = messages[-1]

                        text = extract_text(last_message.content)

                        if text:
                            yield {
                                "event": "message",
                                "data": text,
                            }

            yield {
                "event": "done",
                "data": "completed",
            }

        except Exception as e:
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