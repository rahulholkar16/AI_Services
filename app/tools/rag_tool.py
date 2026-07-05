from langchain.tools import tool;
from app.rag import get_vector_store;

@tool
def search_codebase (repo_full_name: str, query: str) -> str:
    """
    Semantically search the entire codebase.
    Use this for large repos instead of reading files manually.

    Best for:
    - 'authentication logic kahan hai?'
    - 'database connection code'
    - 'error handling patterns'
    - 'API endpoints list'

    repo_full_name format: 'owner/repo'
    Returns relevant code chunks with file paths.
    """
    try:
        store = get_vector_store();
        results = store.similarity_search(query, k=5, filter={"repo_full_name": repo_full_name});

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