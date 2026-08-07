from fastapi import APIRouter;
from app.schemas.chat import ChatRequest;
from app.services.llm import llm;

router = APIRouter();

@router.post("/chat")
async def chat(data: ChatRequest):
    response = llm.invoke(data.message);
    return {
        "response": response.content
    }