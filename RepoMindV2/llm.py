import os;
from dotenv import load_dotenv;
from langchain_groq import ChatGroq;

load_dotenv();

llm = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0,
    max_tokens=3000,
    api_key=os.getenv("GROQ_API_KEY")  
)
