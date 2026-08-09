from app.tools import list_directory, read_file, search_file, search_code, search_codebase;
from .state import State;
from  app.llm import llm;
from langchain_core.messages import (
    SystemMessage, AIMessage, ToolMessage, RemoveMessage
)
from langgraph.prebuilt import ToolNode;
from app.utils.count_tokens import count_tokens;
from app.utils.summarize_model import summarize_model;
from app.utils.cheap_llm import get_cheap_llm;
import uuid;
import asyncio;

tools = [
    search_codebase,
    list_directory,
    read_file,
    search_file,
    search_code,
];

SOFT_TRIGGER_TOKENS = 120_000 
HARD_TRIGGER_TOKENS = 250_000
KEEP_RAW_TURNS = 4             

llm_with_tools = llm.bind_tools(tools);

SYSTEM_PROMPT = """
You are RepoBrain — a GitHub Repository Analysis Agent.

## Your job
Answer questions about a codebase accurately, using tools to find real evidence — never guess or hallucinate file contents, function names, or logic.

## Tool selection
- list_directory: Use once at the start of a new analysis, or when you need to explore a part of the structure you haven't seen yet. Don't call it repeatedly once you know the layout.
- search_file: Use when you know or suspect a filename or path (e.g. "find the config file", "where's auth.py", "locate the Dockerfile").
- search_codebase: Use for conceptual/semantic questions — "how is auth handled", "where is rate limiting implemented". Start here when the query is about a concept, not a specific name.
- search_code: Use when you know (or can guess) an exact function, variable, or class name.
- read_file: Use once search has pointed you to a specific file and you need full context before answering.

Typical flow: list_directory (if needed) → search_file / search_codebase / search_code (narrow down, pick based on what you're looking for) → read_file (confirm) → answer.

## Rules
1. Never answer with code, file paths, or logic you haven't actually retrieved via a tool in this conversation.
2. If a tool call fails or returns nothing (file not found, no search results), say so honestly and try an alternate approach (different search terms, list_directory to re-check structure) — do not fill the gap with a guess.
3. Always cite the file path (and line numbers if available) when referencing specific code.
4. If the question is unrelated to this repository, say so and redirect the user back to repo-scoped questions.
5. Keep answers grounded and concise — summarize what you found, don't paste entire files unless asked.

## Avoid redundant tool calls
- Never call the same tool with the same arguments twice in this conversation — check what you've already looked up before calling a tool again.
- If a file has already been read earlier in this conversation, reuse that content instead of reading it again, unless the user explicitly asks you to re-read it (e.g. after saying they changed the file).
- Once you have enough evidence to answer confidently, stop calling tools and answer — don't keep exploring "just in case."

## Parallel tool calls
If you need to look up multiple independent things (e.g. reading 2 different files, or searching 2 different unrelated terms), call all the relevant tools in the SAME turn instead of one at a time — this saves time. Only call tools sequentially when one result is needed to decide the next call.
Do NOT mention, narrate, or announce that you are making tool calls (e.g. never write things like "(Reading server.js, routes/UserRoute.js in parallel)" in your answer) — just call the tools silently and use their results to write your final answer.

## Output format
- Short explanation in plain language first.
- Relevant code snippet(s) with file path noted above each.
- If multiple files are involved, list them in the order relevant to the explanation.
"""

async def call_model (state: State):
    repo_name = state.get("repo_full_name", "not_specified");
    messages = state["messages"];

    memory_blocks = [
        m.content for m in messages
        if isinstance(m, SystemMessage) and str(m.content).startswith("[Long-term memory]")
    ]
    non_system_message = [m for m in messages if not isinstance(m, SystemMessage)]

    context = f"\n\nCurrent repo: {repo_name}"
    if memory_blocks:
        context += "\n\n" + "\n\n".join(memory_blocks)

    system_msg = SystemMessage(content=SYSTEM_PROMPT + context)
    messages = [system_msg] + non_system_message
    response = await llm_with_tools.ainvoke(messages)

    if response.tool_calls:
        for tc in response.tool_calls:
            print(f"Tool called: {tc['name']} | args: {tc['args']}")
    else:
        print("No tool called — model answered directly")

    return {"messages": [response]};

tool_node = ToolNode(tools);

async def compact_message(state: State) -> dict:
    all_messages = state["messages"]
    non_system = [m for m in all_messages if not isinstance(m, SystemMessage)]

    token_count = count_tokens(non_system)
    if token_count < SOFT_TRIGGER_TOKENS:
        print("\n\nTOKEN COUNT:: ", token_count, "\n\n")
        return {}

    keep_n = 2 if token_count >= HARD_TRIGGER_TOKENS else KEEP_RAW_TURNS
    recent = non_system[-keep_n:]
    old = non_system[:-keep_n]
    if not old:
        return {}

    tool_heavy = [m for m in old if isinstance(m, ToolMessage)]
    other_old = [m for m in old if not isinstance(m, ToolMessage)]

    tool_summary, convo_summary = await asyncio.gather(
        summarize_model(tool_heavy),
        summarize_model(other_old),
    )
    
    combined = "\n\n".join(filter(None, [
        f"Tool findings so far:\n{tool_summary}" if tool_summary else "",
        f"Conversation so far:\n{convo_summary}" if convo_summary else "",
    ]))

    removal = [RemoveMessage(id=m.id) for m in old if m.id is not None]
    summary_msg = AIMessage(content=f"[Compacted summary]:\n{combined}")
    print("====SUMMARY_MSG==== \n", summary_msg.content)
    return {"messages": removal + [summary_msg]}


def _memory_namespace(repo_id: str, user_id: str, kind: str) -> tuple:
    return ("repo", repo_id, "user", user_id, kind)


async def retrieve_memory(state: State, *, store) -> dict:
    repo_id = state.get("repo_id", "")
    user_id = state.get("user_id", "")
    if not repo_id or not user_id:
        return {}

    last_user_text = ""
    for m in reversed(state["messages"]):
        if m.type == "human":
            last_user_text = m.content
            break

    try:
        facts = await store.asearch(_memory_namespace(repo_id, user_id, "facts"), limit=20)
        episodes = await store.asearch(
            _memory_namespace(repo_id, user_id, "episodes"),
            query=last_user_text,
            limit=5,
        )
    except Exception as e:
        print(f"Retrieve_memory failed, continuing without memory: {e!r}")
        return {}

    if not facts and not episodes:
        return {}

    facts_text = "\n".join(f"- {f.value.get('content', '')}" for f in facts)
    episodes_text = "\n".join(f"- {e.value.get('content', '')}" for e in episodes)

    memory_block = "\n\n".join(filter(None, [
        f"Known facts about this repo:\n{facts_text}" if facts_text else "",
        f"Relevant past interactions:\n{episodes_text}" if episodes_text else "",
    ]))

    return {"messages": [SystemMessage(content=f"[Long-term memory]:\n{memory_block}")]}


FACT_EXTRACTOR_PROMPT = """You are filtering an AI coding assistant's answer for durable, \
reusable facts about a GitHub repository — things like tech stack, frameworks, architecture, \
database, deployment target, or key conventions that would still be true and useful in a \
future, unrelated conversation about this repo.

Question: {question}
Answer: {answer}

If the answer contains such a durable fact, reply with ONLY that fact, rewritten as one \
concise, self-contained sentence (no "the answer says" framing).
If it does NOT contain a durable, reusable fact (e.g. it's a one-off code explanation, a \
specific line/function walkthrough, or advice that isn't really about this repo), reply with \
exactly: NONE
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


async def _extract_fact(question: str, answer: str) -> str | None:
    cheap_llm = get_cheap_llm(max_tokens=200)
    prompt = FACT_EXTRACTOR_PROMPT.format(
        question=_content_to_text(question), answer=_content_to_text(answer)
    )
    resp = await cheap_llm.ainvoke(prompt)
    text = _content_to_text(resp.content).strip()
    if not text or text == "NONE":
        return None
    return text


async def _extract_and_save_fact(question, answer, repo_id, user_id, store):
    try:
        fact = await _extract_fact(question, answer)
        if fact:
            await store.aput(
                _memory_namespace(repo_id, user_id, "facts"),
                str(uuid.uuid4()),
                {"content": fact},
            )
    except Exception as e:
            print(f"Fact extraction/save failed: {e!r}")

async def write_memory(state: State, *, store) -> dict:
    repo_id = state.get("repo_id", "")
    user_id = state.get("user_id", "")
    if not repo_id or not user_id:
        return {}

    last_user = next((m for m in reversed(state["messages"]) if m.type == "human"), None)
    last_ai = next((m for m in reversed(state["messages"]) if isinstance(m, AIMessage)), None)

    if last_user and last_ai:
        episode_content = f"Q: {_content_to_text(last_user.content)}\nA: {_content_to_text(last_ai.content)}"
        try:
            await store.aput(
                _memory_namespace(repo_id, user_id, "episodes"),
                str(uuid.uuid4()),
                {"content": episode_content},
            )
        except Exception as e:
            print(f"Failed to save episode, skipping: {e!r}")

        task = asyncio.create_task(
            _extract_and_save_fact(last_user.content, last_ai.content, repo_id, user_id, store)
        )
        task.add_done_callback(_log_task_exception)

    return {}


def _log_task_exception(task: asyncio.Task):
    if task.cancelled():
        return
    exc = task.exception()
    if exc:
        print(f"Background fact-extraction task failed: {exc!r}")