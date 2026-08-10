from app.rag.retrive import search_repo;
from app.services.llm import llm;
from app.prompt.prompt import promt;

def ask_question(question: str):
    docs = search_repo(question);
    context = "\n\n".join([doc.page_content for doc in docs]);
    prompt = promt(context, question);
    res = llm.invoke(prompt);
    return res.content;
