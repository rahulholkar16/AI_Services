import os;
from dotenv import load_dotenv;
# from langchain_groq import ChatGroq;
from langchain.chat_models import init_chat_model

load_dotenv();

llm = init_chat_model(
    model="gemini-3.1-flash-lite",
    model_provider="google_genai",   
    temperature=0,
    max_tokens=3000,
    api_key=os.getenv("GEMINI_API_KEY"),
)

# llm = ChatGroq(
#     model="openai/gpt-oss-120b",
#     temperature=0,
#     max_tokens=3000,
#     api_key=os.getenv("GROQ_API_KEY")  
# );
