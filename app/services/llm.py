from dotenv import load_dotenv;
import os;
# from langchain_google_genai import ChatGoogleGenerativeAI;
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.checkpoint.memory import MemorySaver
from langchain.agents import create_agent;
from langchain.agents.middleware import SummarizationMiddleware;
from app.tools.tools import list_directory, search_code, search_file, read_file, search_codebase, search_bugs_in_file
from langchain_groq import ChatGroq
load_dotenv();
os.environ["GROQ_API_KEY"] = os.getenv("GROQ_API_KEY");
# llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite");

llm = ChatGroq(
    model="qwen/qwen3-32b",  # Free, fast, smart
    temperature=0,
    max_tokens=700,
    api_key=os.getenv("GROQ_API_KEY")   
)

tools = [
    search_codebase,
    search_bugs_in_file, 
    list_directory,
    search_file,
    read_file,
    search_code,
]

def create_app_agent(checkpointer):
    return create_agent(
        model=llm,
        tools=tools,
        checkpointer=checkpointer,
        middleware=[
            SummarizationMiddleware(
                model=llm,
                trigger=("tokens", 3500),
                keep=("messages", 6),
                trim_tokens_to_summarize=1800,
            )
        ],
        system_prompt="""
    You are a GitHub Repository Analysis Agent NAME REPO_MIND.

    Your job is to understand repositories.

    Always:
    1. Search files first.
    2. Read files before answering.
    3. Use code evidence.
    4. Never guess.

    IMPORTANT: 
    - Jab user kisi specific feature ki baat kare (submission, payment, auth)
    toh PEHLE search_file() se us feature ki files dhundho
    - Phir un specific files ko read_file() se padho  
    - Kabhi bhi similar naam wali files mat return karo
    - Agar unclear ho toh user se poocho: "Kaunsa submission feature?
    Student assignment wala ya form submission wala?"
    """
    )
