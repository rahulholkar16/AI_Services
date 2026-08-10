from pathlib import Path
from langchain.tools import tool
from app.github.getRepo import get_repository
from app.rag.vector_store import get_vector_store
from app.tools.safe_return import safe_return

IGNORE_DIRS = {
    ".git", "node_modules", ".next", "dist",
    "build", "__pycache__", ".venv", ".env"
}

# Sirf ye files padhenge — binary skip
TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".html", ".css", ".json", ".md", ".txt",
    ".yaml", ".yml", ".env.example", ".sh",
    ".java", ".go", ".rs", ".cpp", ".c", ".h"
}

MAX_FILE_CHARS = 1200   # Per file limit
MAX_FILES_LIST = 80     # Directory listing limit
MAX_SEARCH_RESULTS = 6  # Search results limit
MAX_TOOL_CHARS = 3600   # Hard cap for a single tool response
MAX_CHUNK_CHARS = 1200  # Per retrieved vector chunk


def trim_text(text: str, max_chars: int = MAX_TOOL_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n... [truncated to stay within model token limits]"


def trim_chunk(text: str) -> str:
    return trim_text(text, MAX_CHUNK_CHARS)


def is_text_file(path: Path) -> bool:
    return path.suffix.lower() in TEXT_EXTENSIONS


def get_repo() -> Path:
    return Path(get_repository())


# ─────────────────────────────────────────
# TOOL 1: Directory listing — smart & slim
# ─────────────────────────────────────────
@tool
def list_directory() -> list[str]:
    """
    List repository text files only.
    Use this first to understand project structure.
    Returns max 80 relevant files.
    """
    repo = get_repo()
    result = []

    for path in repo.rglob("*"):
        if any(part in IGNORE_DIRS for part in path.parts):
            continue
        if path.is_file() and is_text_file(path):
            result.append(str(path.relative_to(repo)))

    return safe_return(sorted(result)[:MAX_FILES_LIST])


# ─────────────────────────────────────────
# TOOL 2: File search — naam se dhundho
# ─────────────────────────────────────────
@tool
def search_file(query: str) -> list[str]:
    """
    Search files by name.
    Use for finding auth, db, api, config files.
    Example query: 'auth', 'database', 'middleware'
    """
    repo = get_repo()
    matches = []
    query = query.lower()

    for file in repo.rglob("*"):
        if any(part in IGNORE_DIRS for part in file.parts):
            continue
        if not file.is_file() or not is_text_file(file):
            continue
        if query in file.name.lower():
            matches.append(str(file.relative_to(repo)))

    return safe_return(sorted(matches)[:MAX_SEARCH_RESULTS])


# ─────────────────────────────────────────
# TOOL 3: File reader — chunked & limited
# ─────────────────────────────────────────
@tool
def read_file(file_path: str, start_line: int = 1, end_line: int = 100) -> str:
    """
    Read specific lines from a file.
    Always read in chunks — default is lines 1-100.
    Use start_line and end_line to navigate large files.
    Example: read_file('src/auth.py', 1, 100)
             read_file('src/auth.py', 101, 200)
    """
    file = get_repo() / file_path

    if not file.exists():
        return f"File not found: {file_path}"
    if not file.is_file():
        return f"Not a file: {file_path}"
    if not is_text_file(file):
        return f"Binary file skipped: {file_path}"

    try:
        lines = file.read_text(encoding="utf-8", errors="ignore").splitlines()
        total = len(lines)

        # Clamp ranges
        start = max(1, start_line) - 1
        end = min(total, end_line)

        chunk = "\n".join(lines[start:end])

        # Hard cap on chars
        if len(chunk) > MAX_FILE_CHARS:
            chunk = chunk[:MAX_FILE_CHARS] + "\n... [truncated]"

        return trim_text(
            f"File: {file_path} "
            f"(lines {start+1}-{end} of {total})\n\n"
            + chunk
        )

    except Exception as e:
        return f"Error reading file: {str(e)}"


# ─────────────────────────────────────────
# TOOL 4: Code search — efficient grep
# ─────────────────────────────────────────
@tool
def search_code(query: str) -> list[dict]:
    """
    Search for a keyword/pattern inside code files.
    Returns file path + matching line number + snippet.
    Use for finding specific functions, imports, patterns.
    Example: 'JWT', 'SQL query', 'fetch(', 'useState'
    """
    repo = get_repo()
    matches = []
    query_lower = query.lower()

    for path in repo.rglob("*"):
        if any(part in IGNORE_DIRS for part in path.parts):
            continue
        if not path.is_file() or not is_text_file(path):
            continue

        try:
            lines = path.read_text(
                encoding="utf-8", errors="ignore"
            ).splitlines()

            for i, line in enumerate(lines, 1):
                if query_lower in line.lower():
                    matches.append({
                        "file": str(path.relative_to(repo)),
                        "line": i,
                        "snippet": line.strip()[:200]  # sirf 200 chars
                    })

                if len(matches) >= MAX_SEARCH_RESULTS:
                    return matches  # jaldi rok do

        except:
            continue

    return safe_return(matches)

@tool
def search_codebase(query: str) -> str:
    """
    Semantically search the entire codebase.
    Use this for large repos instead of reading files manually.
    
    Best for:
    - 'authentication logic kahan hai?'
    - 'database connection code'
    - 'error handling patterns'
    - 'API endpoints list'
    - 'bug in payment flow'
    
    Returns relevant code chunks with file paths.
    """
    vectorstore = get_vector_store()

    # Relevant chunks dhundho
    results = vectorstore.similarity_search_with_score(
        query=query,
        k=3  # Keep Groq requests below the on-demand TPM cap
    )

    if not results:
        return "No relevant code found for this query."

    output = []
    for doc, score in results:
        # Score 0 = perfect match, 1 = no match
        relevance = round((1 - score) * 100, 1)

        output.append(
            f"📄 File: {doc.metadata['source']} "
            f"(relevance: {relevance}%)\n"
            f"```\n{trim_chunk(doc.page_content)}\n```"
        )

    return trim_text("\n\n---\n\n".join(output))


@tool
def search_bugs_in_file(file_path: str) -> str:
    """
    Specific file ke related code chunks dhundho
    aur bug patterns search karo.
    Use when you know which file has issues.
    """
    vectorstore = get_vector_store()

    # File ke chunks filter karo
    results = vectorstore.similarity_search(
        query="bug error exception vulnerability",
        k=3,
        filter={"source": file_path}
    )

    if not results:
        return f"No chunks found for: {file_path}"

    output = []
    for doc in results:
        output.append(
            f"```\n{trim_chunk(doc.page_content)}\n```"
        )

    return trim_text(f"File: {file_path}\n\n" + "\n\n---\n\n".join(output))
