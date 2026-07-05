from app.tools import list_directory, read_file, search_file, search_code, search_codebase;
from .state import State;
from  app.llm import llm;
from langchain_core.messages import SystemMessage;
from langgraph.prebuilt import ToolNode;

tools = [
    search_codebase,
    list_directory,
    read_file,
    search_file,
    search_code,
];

llm_with_tools = llm.bind_tools(tools);

SYSTEM_PROMPT = """
You are RepoBrain — a GitHub Repository Analysis Agent.

Always:
1. Use list_directory first to understand project structure.
2. Use search_codebase for concepts/features (semantic search).
3. Use search_code for exact function/variable names.
4. Use read_file for specific file contents.
5. Never guess — always use tools to find evidence.
""";

def call_model (state: State):
    messages = state["messages"];
    if not any(isinstance(m, SystemMessage) for m in messages):
        context = f"\n\nCurrent repo: {state['repo_full_name']}"
        messages = [SystemMessage(content=SYSTEM_PROMPT + context)] + messages

    response = llm_with_tools.invoke(messages)
    return {"messages": [response]};

tool_node = ToolNode(tools);