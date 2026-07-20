from app.tools import list_directory, read_file, search_file, search_code, search_codebase;
from .state import State;
from  app.llm import llm;
from langchain_core.messages import (
    SystemMessage, AIMessage, ToolMessage, RemoveMessage
)
from langgraph.prebuilt import ToolNode;
from app.utils.count_tokens import count_tokens;
from app.utils.summarize_model import summarize_model;

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

## Output format
- Short explanation in plain language first.
- Relevant code snippet(s) with file path noted above each.
- If multiple files are involved, list them in the order relevant to the explanation.
"""

def call_model (state: State):
    repo_name = state.get("repo_full_name", "not_specified");
    messages = state["messages"];
    non_system_message = [m for m in messages if not isinstance(m, SystemMessage)]
    context = f"\n\nCurrent repo: {repo_name}"
    system_msg = SystemMessage(content=SYSTEM_PROMPT + context)
    messages = [system_msg] + non_system_message
    response = llm_with_tools.invoke(messages)

    if response.tool_calls:
        for tc in response.tool_calls:
            print(f"Tool called: {tc['name']} | args: {tc['args']}")
    else:
        print("No tool called — model answered directly")

    return {"messages": [response]};

tool_node = ToolNode(tools);

def compact_message(state: State) -> dict:
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

    tool_summary = summarize_model(tool_heavy) if tool_heavy else ""
    convo_summary = summarize_model(other_old) if other_old else ""

    combined = "\n\n".join(filter(None, [
        f"Tool findings so far:\n{tool_summary}" if tool_summary else "",
        f"Conversation so far:\n{convo_summary}" if convo_summary else "",
    ]))

    removal = [RemoveMessage(id=m.id) for m in old if m.id is not None]
    summary_msg = AIMessage(content=f"[Compacted summary]:\n{combined}")
    print("====SUMMARY_MSG==== \n", summary_msg.content)
    return {"messages": removal + [summary_msg]}