from fastapi import APIRouter, HTTPException;
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
    try:
        repo_full_name = extract_full_name(request.repo_url)

        config = {"configurable": {"thread_id": request.thread_id}}
        print("Thread ID:: ", request.thread_id);
        response = await state.agent.ainvoke(
            {
                "messages": [HumanMessage(content=request.question)],
                "repo_url": request.repo_url,
                "repo_full_name": repo_full_name,
                "repo_id": request.repo_id,
                "thread_id": request.thread_id,
                "pr_pending": None,
            },
            config=config
        )

        answer = extract_text(response["messages"][-1].content)

        print("Answer:: ", answer)
        return {
            "answer": answer,
            "thread_id": request.thread_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
