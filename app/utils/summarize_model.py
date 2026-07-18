import os;
from dotenv import load_dotenv;
from langchain_core.messages import BaseMessage;
from langchain.chat_models import init_chat_model;

load_dotenv();

def summarize_with_cheap_model(messages: list[BaseMessage]) -> str:
    
    cheap_llm = init_chat_model(
        model="gemini-2.5-flash-lite",
        model_provider="google_genai",
        temperature=0,
        max_tokens=800,
        api_key=os.getenv("GEMINI_API_KEY_S"),
    )

    text_blob = "\n\n".join(
        f"[{type(m).__name__}] {m.content}" for m in messages
    )

    prompt = (
        "Summarize this agent transcript. Preserve ALL specific file paths, "
        "function/class names, and concrete findings exactly as stated — "
        "these must remain retrievable later. Compress narrative/reasoning "
        "text, but never compress or drop specific identifiers. "
        "Keep under 300 words unless more file paths need listing:\n\n"
        f"{text_blob}"
    )

    resp = cheap_llm.invoke(prompt)
    return resp.content