from langchain_core.messages import BaseMessage;
from app.utils.cheap_llm import get_cheap_llm;

async def summarize_model(messages: list[BaseMessage]) -> str:
    
    cheap_llm = get_cheap_llm(max_tokens=800)

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

    resp = await cheap_llm.ainvoke(prompt)
    return resp.content