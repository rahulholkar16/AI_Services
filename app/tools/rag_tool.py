from typing import Annotated;
from langchain.tools import tool;
from langgraph.prebuilt import InjectedState;
from app.rag import get_index, get_embeddings;
from app.graph.state import State;

@tool
async def search_codebase (query: str, state: Annotated[State, InjectedState], extension: str | None = None,) -> str:
    """
    Semantically search the entire codebase.
    Use this for large repos instead of reading files manually.

    Best for:
    - 'authentication logic kahan hai?'
    - 'database connection code'
    - 'error handling patterns'
    - 'API endpoints list'

    Args:
        query: Natural language search query describing what to find.
        extension: Optional file extension to restrict the search to a
            single language/file type, including the leading dot
            (e.g. ".py", ".ts", ".tsx", ".json", ".md"). Set this only
            when the user's request clearly targets one file type
            (e.g. "python me database connection code dhundo" ->
            extension=".py", "frontend component dhundo" -> extension=".tsx").
            Leave as None for a general search across all file types.

    Returns relevant code chunks with file paths.
    """
    try:
        filter_dict = {}
        if extension:
            filter_dict["extension"] = {"$eq": extension}

        repo_full_name = state["repo_full_name"]
        branch = state.get("branch")
        namespace = f"{repo_full_name}#{branch}" if branch else repo_full_name

        embeddings = get_embeddings()
        query_vector = await embeddings.aembed_query(query)

        index = await get_index()
        response = await index.query(
            vector=query_vector,
            top_k=5,
            namespace=namespace,
            include_metadata=True,
            filter=filter_dict or None
        )

        matches = response.get("matches", [])
        if not matches:
            return f"No relevant code found for: {query}";

        output = [];
        for match in matches:
            relevance = round(match.get("score", 0) * 100, 1)
            metadata = match.get("metadata", {}) or {}
            content = (metadata.get("text") or "").strip()

            if not content:
                continue

            output.append(
                f"📄 File: {metadata.get('source', 'unknown')} "
                f"(relevance: {relevance}%)\n"
                f"```\n{content}\n```"
            )
        return "\n\n---\n\n".join(output) if output else "No relevant code found."

    except Exception as e:
        return f"Error searching codebase: {str(e)}";
