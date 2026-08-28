from typing import TypedDict, Annotated;
from langchain_core.messages import BaseMessage;
from langgraph.graph.message import add_messages;

class State (TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    repo_url: str
    repo_full_name: str
    repo_id: str
    user_id: str
    thread_id: str
    pr_pending: dict | None
    branch: str

