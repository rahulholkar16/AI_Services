from typing import Annotated;
from langchain.tools import tool;
from langgraph.prebuilt import InjectedState;
from app.rag import get_index, get_embeddings;
from app.graph.state import State;
from app.utils import rerank;
from app.utils import cache_get, cache_set;

MAX_CONTENT_PER_MATCH = 800
CANDIDATE_POOL_SIZE = 20
FINAL_RESULT_COUNT = 5

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

        cache_key = f"codebase_search:{namespace}:{extension or 'all'}:{query}"
        cached = await cache_get(cache_key)
        if cached:
            return cached

        embeddings = get_embeddings()
        query_vector = await embeddings.aembed_query(query)

        index = await get_index()
        response = await index.query(
            vector=query_vector,
            top_k=CANDIDATE_POOL_SIZE,
            namespace=namespace,
            include_metadata=True,
            filter=filter_dict or None
        )

        matches = response.get("matches", [])
        if not matches:
            return f"No relevant code found for: {query}";

        candidates = []
        for match in matches:
            metadata = match.get("metadata", {}) or {}
            content = (metadata.get("text") or "").strip()
            if content:
                candidates.append((content, metadata))

        if not candidates:
            return f"No relevant code found for: {query}";

        candidate_texts = [c[0] for c in candidates]
        reranked_indices = await rerank(query, candidate_texts, top_n=FINAL_RESULT_COUNT)

        output = [];
        for idx in reranked_indices:
            content, metadata = candidates[idx]

            if len(content) > MAX_CONTENT_PER_MATCH:
                content = content[:MAX_CONTENT_PER_MATCH] + "\n...[truncated]"

            output.append(
                f"📄 File: {metadata.get('source', 'unknown')}\n"
                f"```\n{content}\n```"
            )

        if not output:
            return "No relevant code found."

        result = "\n\n---\n\n".join(output)
        await cache_set(cache_key, result, ttl=900)
        return result

    except Exception as e:
        return f"Error searching codebase: {str(e)}";
