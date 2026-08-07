from typing import TypedDict, Dict, Any, List;

agent=None

class State (TypedDict):
    repo_url: str
    repo_path: str
    user_query: str
    plan: Dict[str, Any]
    retrieved_chunks: List[str]
    tool_results: List[Dict[str, Any]]
    final_response: str
    error: str | None
