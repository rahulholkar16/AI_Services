import os
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model

load_dotenv()


def get_cheap_llm(max_tokens: int = 200):
    return init_chat_model(
        model="gemini-3.1-flash-lite",
        model_provider="google_genai",
        temperature=0,
        max_tokens=max_tokens,
        api_key=os.getenv("GEMINI_API_KEY"),
    )
