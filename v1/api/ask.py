from fastapi import APIRouter;
from app.schemas.ask import AskRequest;
from app.services.qa import ask_question;

router = APIRouter(prefix="/ask", tags=["Ask"]);

@router.post("")
async def ask(data: AskRequest):
    answer = ask_question(data.question);
    return {
        "answer": answer
    }