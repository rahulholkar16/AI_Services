import logging
from pydantic import BaseModel, Field
from .cheap_llm import get_cheap_llm
from .fact_extractor import _content_to_text

logger = logging.getLogger(__name__)

EPISODE_EXTRACTOR_PROMPT = """You are extracting episodic memories from an AI coding assistant.

An episodic memory represents a meaningful event, decision, change, or interaction
that may be useful in a future conversation about this GitHub repository.

Store an episode ONLY when the interaction contains something worth remembering.

GOOD episodic memories:
- A bug or technical problem was fixed
- An important implementation decision was made
- An architectural decision was made
- A deployment/configuration problem was solved
- A significant repository change was discussed or completed
- The user explicitly asked to remember something
- A meaningful debugging discovery was made
- A specific approach was chosen over another approach

DO NOT store:
- Greetings or casual conversation
- Simple explanations of code
- Generic programming questions
- Trivial syntax questions
- One-off code walkthroughs
- Generic advice
- Repeated information that has no new event
- Questions that do not represent a meaningful repository event

Important:
An episodic memory is about WHAT HAPPENED, not a permanent fact.

Example:

Question:
"Why was the Docker container failing?"

Answer:
"The container could not connect to PostgreSQL because both services
were not on the same Docker network. We fixed it by adding both services
to the same Compose network."

Good episode:
"Resolved a Docker networking issue by placing the application and
PostgreSQL services on the same Compose network."

Bad episode:
"The project uses Docker and PostgreSQL."

The second one is a FACT, not an episode.

Question:
{question}

Answer:
{answer}

Return:
- should_store: whether this interaction deserves episodic memory
- topic: short snake_case category
- content: concise, self-contained description of what happened
- importance: integer from 1 to 5

Importance:
1 = almost trivial
2 = minor useful event
3 = moderately useful event
4 = important debugging/implementation event
5 = major architectural decision or explicitly requested memory

Keep content concise. Usually one sentence.
"""

class ExtractedEpisode(BaseModel):
    should_store: bool = Field(
        description=(
            "True only if this interaction contains a meaningful "
            "event, decision, change, or debugging outcome worth remembering"
        )
    )

    topic: str = Field(
        description=(
            "Short snake_case category such as "
            "docker_debugging, auth_fix, architecture_decision, "
            "deployment, database_migration, api_change"
        )
    )

    content: str = Field(
        description=(
            "One concise, self-contained sentence describing "
            "what happened"
        )
    )

    importance: int = Field(
        description="Importance score from 1 to 5"
    )

async def _extract_episode(question: str, answer: str) -> ExtractedEpisode | None:
    cheap_llm = get_cheap_llm(max_tokens=250)
    structured_llm = cheap_llm.with_structured_output(ExtractedEpisode)

    prompt = EPISODE_EXTRACTOR_PROMPT.format(
        question=_content_to_text(question),
        answer=_content_to_text(answer),
    )

    try:
        res = await structured_llm.ainvoke(prompt)
    except Exception as e:
        logger.warning("Episode extraction structured-output failed: %r", e)
        return None

    if not res or not res.should_store:
        return None

    topic = res.topic.strip().lower().replace(" ", "_")
    content = res.content.strip()

    importance = max(
        1,
        min(5, res.importance),
    )

    if not topic or not content:
        return None

    res.topic = topic
    res.content = content
    res.importance = importance

    return res

    
