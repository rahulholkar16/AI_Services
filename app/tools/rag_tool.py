from typing import Annotated;
from langchain.tools import tool;
from langgraph.prebuilt import InjectedState;
from app.rag import get_vector_store;
from app.graph.state import State;

@tool
def search_codebase (query: str, state: Annotated[State, InjectedState]) -> str:
    """
    Semantically search the entire codebase.
    Use this for large repos instead of reading files manually.

    Best for:
    - 'authentication logic kahan hai?'
    - 'database connection code'
    - 'error handling patterns'
    - 'API endpoints list'

    Returns relevant code chunks with file paths.
    """
    try:
        repo_full_name = state["repo_full_name"]
        branch = state.get("branch")
        namespace = f"{repo_full_name}#{branch}" if branch else repo_full_name

        store = get_vector_store();
        results = store.similarity_search_with_score(query, k=5, namespace=namespace);

        if not results:
            return f"No relevant code found for: {query}";

        output = [];
        for doc, score in results:
            relevance = round((1 - score) * 100, 1)
            content = doc.page_content.strip()

            if not content:
                continue

            output.append(
                f"📄 File: {doc.metadata.get('source', 'unknown')} "
                f"(relevance: {relevance}%)\n"
                f"```\n{content}\n```"
            )
        return "\n\n---\n\n".join(output) if output else "No relevant code found."

    except Exception as e:
        return f"Error searching codebase: {str(e)}";
