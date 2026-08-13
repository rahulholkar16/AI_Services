import logging
from pydantic import BaseModel, Field
from .cheap_llm import get_cheap_llm

logger = logging.getLogger(__name__)

FACT_EXTRACTOR_PROMPT = """You are filtering an AI coding assistant's answer for durable, \
reusable facts about a GitHub repository — things like tech stack, frameworks, architecture, \
database, deployment target, or key conventions that would still be true and useful in a \
future, unrelated conversation about this repo.

Question: {question}
Answer: {answer}

Set has_fact to true only if the answer contains such a durable fact. If true, set topic to a \
short snake_case category label (reuse the same label for the same category every time — e.g. \
tech_stack, auth_mechanism, database, deployment, folder_structure, api_design, testing_setup, \
coding_conventions), and fact to one concise, self-contained sentence stating it.

Set has_fact to false if it's a one-off code explanation, a specific line/function walkthrough, \
or advice that isn't really about this repo — in that case leave topic and fact empty.
"""

def _content_to_text(content) -> str:
    """AIMessage.content string ya list-of-blocks (Gemini structured content)
    dono ho sakta hai — dono ko plain string mein normalize karta hai."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                parts.append(block.get("text", ""))
        return "\n".join(p for p in parts if p)
    return str(content) if content else ""

class ExtractedFact(BaseModel):
    has_fact: bool = Field(description="True if the answer contains a durable, reusable fact about this repo; false otherwise")
    topic: str = Field(description="Short snake_case category label, e.g. tech_stack, auth_mechanism, database, deployment")
    fact: str = Field(description="One concise, self-contained sentence stating the durable fact")

async def _extract_fact(question: str, answer: str) -> tuple[str, str] | None:
    cheap_llm = get_cheap_llm(max_tokens=200)
    structured_llm = cheap_llm.with_structured_output(ExtractedFact)
    prompt = FACT_EXTRACTOR_PROMPT.format(
                question=_content_to_text(question), answer=_content_to_text(answer)
            )
    try:
        res = await structured_llm.ainvoke(prompt)
    except Exception as e:
        logger.warning("Fact extraction structured-output failed: %r", e)
        return None

    if not res or not res.has_fact:
        return None

    topic = res.topic.strip().lower().replace(" ", "_")
    fact = res.fact.strip()
    if not topic or not fact:
        return None

    return topic, fact
