from app.tools import list_directory, read_file, search_file, search_code, search_codebase, fetch_all_pull_request, get_pr_status, get_pr_diff, propose_pull_request;
from .state import State;
from  app.llm import llm;
from langchain_core.messages import (
    SystemMessage, AIMessage, ToolMessage, RemoveMessage
)
from langgraph.prebuilt import ToolNode;
from app.utils import count_tokens, summarize_model, _save_fact, _memory_namespace, _content_to_text, _save_episode, log_task_exception, MEMORY_PREFIX, find_old_memory_messages
import asyncio;
import logging;

logger = logging.getLogger(__name__)

tools = [
    search_codebase,
    list_directory,
    read_file,
    search_file,
    search_code,
    fetch_all_pull_request,
    get_pr_status,
    get_pr_diff,
    propose_pull_request,
];

SOFT_TRIGGER_TOKENS = 60000
HARD_TRIGGER_TOKENS = 120000
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
- Before calling search_codebase (or any search tool) for a specific function, class, variable, or symbol, first check whether its code is already visible in this conversation — from an earlier read_file, list_directory, or a previous search result. If the file containing it has already been read in full, that file's content already covers everything in it; do not search_codebase for individual names/symbols defined inside a file you've already read (e.g. after read_file("app/middleware/auth.py"), do NOT then run separate search_codebase calls for "JWKS_URL", "_verify_token", "PyJWKClient", "class AuthMiddleware" — all of that is already in the file you have). Only search for something genuinely not yet seen in this conversation.
- Once you have enough evidence to answer confidently, stop calling tools and answer — don't keep exploring "just in case."

## Parallel tool calls
If you need to look up multiple independent things (e.g. reading 2+ different files, or searching 2+ unrelated terms), call ALL of those tools together in the SAME turn — issue multiple tool_calls in one response instead of calling one, waiting for the result, then calling the next. Each extra round-trip re-sends the entire conversation so far, so calling tools one at a time when they don't depend on each other wastes both time and tokens. Only call tools sequentially when one result is genuinely needed to decide the next call's arguments (e.g. you must list_directory before you know which file to read).

Example — analyzing a system made of several files (e.g. "review my graph/pipeline/module"):
- WRONG: read_file(builder.py) → wait for result → read_file(nodes.py) → wait for result → read_file(state.py)
- RIGHT: read_file(builder.py) + read_file(nodes.py) + read_file(state.py) all issued as tool_calls in the SAME response, since none of these reads depends on another's content.
This applies any time you already know (from list_directory, search_file, or search_codebase results, or from the user's message) which 2+ files or queries you need — issue them together, don't trickle them out one per turn.

Do NOT mention, narrate, or announce that you are making tool calls (e.g. never write things like "(Reading server.js, routes/UserRoute.js in parallel)" in your answer) — just call the tools silently and use their results to write your final answer.

## Pull request tools
- fetch_all_pull_request: Use to list open/closed/all PRs in the current repo.
- get_pr_status: Use to check a specific PR's mergeable state, checks, commit/file counts. Requires a PR number — ask the user if they haven't given one.
- get_pr_diff: Use before reviewing, summarizing, or analyzing what a specific PR changes.
- propose_pull_request: Use ONLY when the user explicitly asks to open/create a PR. This never creates the PR directly — it only stages a proposal (title, description, branches) and asks the user to confirm. You must write a clear title and description yourself based on context. NEVER call this more than once for the same request without new user input, NEVER tell the user the PR has been created after calling this (it hasn't), and NEVER attempt to create a PR through any other means. If the user hasn't given required info (e.g. which branch), ask them — do not guess.

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
        if isinstance(m, SystemMessage) and str(m.content).startswith(MEMORY_PREFIX)
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
            logger.debug("Tool called: %s | args: %s", tc['name'], tc['args'])
    else:
        logger.debug("No tool called — model answered directly")

    return {"messages": [response]};

tool_node = ToolNode(tools);

async def compact_message(state: State) -> dict:
    all_messages = state["messages"]
    non_system = [m for m in all_messages if not isinstance(m, SystemMessage)]

    token_count = count_tokens(non_system)
    if token_count < SOFT_TRIGGER_TOKENS:
        logger.debug("TOKEN COUNT:: %s", token_count)
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
    logger.debug("====SUMMARY_MSG====\n%s", summary_msg.content)
    return {"messages": removal + [summary_msg]}

async def retrieve_memory(state: State, *, store) -> dict:
    repo_id = state.get("repo_id", "")
    user_id = state.get("user_id", "")
    if not repo_id or not user_id:
        return {}

    last_user_text = next(
        (m.content for m in reversed(state["messages"]) if m.type == "human"),
        "",
    )

    removal = find_old_memory_messages(state["messages"])

    try:
        facts, episodes = await asyncio.gather(
            store.asearch(
                _memory_namespace(repo_id, user_id, "facts"),
                query=last_user_text,
                limit=20,
            ),
            store.asearch(
                _memory_namespace(repo_id, user_id, "episodes"),
                query=last_user_text,
                limit=5,
            ),
        )
    except Exception as e:
        logger.warning("retrieve_memory failed, continuing without memory: %r", e)
        return {"messages": removal}

    if not facts and not episodes:
        logger.debug("No facts/episodes found for repo_id=%s", repo_id)
        return {"messages": removal}

    facts_text = "\n".join(f"- {f.value.get('content', '')}" for f in facts)
    episodes_text = "\n".join(f"- {e.value.get('content', '')}" for e in episodes)

    memory_block = "\n\n".join(filter(None, [
        f"Known facts about this repo:\n{facts_text}" if facts_text else "",
        f"Relevant past interactions:\n{episodes_text}" if episodes_text else "",
    ]))

    logger.debug(
        "Injected memory: %d fact(s), %d episode(s), replaced %d old block(s)",
        len(facts), len(episodes), len(removal),
    )

    return {"messages": removal + [SystemMessage(content=f"{MEMORY_PREFIX}:\n{memory_block}")]}

async def write_memory(state: State, *, store) -> dict:
    repo_id = state.get("repo_id", "")
    user_id = state.get("user_id", "")
    if not repo_id or not user_id:
        return {}

    last_user = next((m for m in reversed(state["messages"]) if m.type == "human"), None)
    last_ai = next((m for m in reversed(state["messages"]) if isinstance(m, AIMessage)), None)

    if last_user and last_ai:
        episode_task = asyncio.create_task(
            _save_episode(last_user.content, last_ai.content, repo_id, user_id, store)
        )

        episode_task.add_done_callback(log_task_exception)
        
        fact_task = asyncio.create_task(
            _save_fact(last_user.content, last_ai.content, repo_id, user_id, store)
        )

        fact_task.add_done_callback(log_task_exception)

    return {}