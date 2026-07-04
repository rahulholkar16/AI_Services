import requests;
from langchain.tools import tool;
import base64;

HEADERS = {
    # In future We add a Token based HEADER
    "Accept": "application/vnd.github+json"
}

IGNORE_DIRS = {
    ".git", "node_modules", ".next", "dist",
    "build", "__pycache__", ".venv"
}

ALLOW_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx",
    ".json", ".md", ".yaml", ".yml", ".toml",
    ".css", ".html", ".sh", ".go", ".rs",
    ".java", ".c", ".cpp", ".c++", ".h", ".prisma"
}

# List ALL files in GitHub repo recursively
@tool
def list_directory (repo_full_name: str):
    """
    List ALL files in a GitHub repo recursively.
    Use this first to understand complete project structure.
    repo_full_name format: 'owner/repo'
    """
    try:
        url = f"https://api.github.com/repos/{repo_full_name}/git/trees/HEAD?recursive=1";
        res = requests.get(url, headers=HEADERS);

        if not res.ok:
            return f"Failed to list repo: {res.status_code}"
        
        data = res.json()
        tree = data.get("tree", [])
        if not tree:
            return "Empty repository."
        
        output = []
        for item in tree:
            path = item["path"]

            if any(part in IGNORE_DIRS for part in path.split("/")):
                continue

            if item["type"] == "tree":
                output.append(f"📁 {path}")
            elif item["type"] == "blob":
                ext = "." + path.split(".")[-1].lower() if "." in path else ""
                if ext in ALLOW_EXTENSIONS:
                    output.append(f"📄 {path}")

        result = "\n".join(output[:100])
        return result if result else "No relevant files found."

    except Exception as e:
        return f"Error listing directory: {str(e)}"

# Read a specific file from GitHub repo  
@tool
def read_file (repo_full_name: str, file_path: str):
    """
    Read a specific file from GitHub repo.
    Use for understanding implementation details.
    repo_full_name format: 'owner/repo'
    file_path: 'src/auth.ts', 'app/page.tsx'
    """
    try:
        url = f"https://api.github.com/repos/{repo_full_name}/contents/{file_path}"
        res = requests.get(url, headers=HEADERS)

        if not res.ok:
            return f"File not found: {file_path}"

        data = res.json()

        # Binary file skip karo
        ext = "." + file_path.split(".")[-1].lower() if "." in file_path else ""
        if ext not in ALLOW_EXTENSIONS:
            return f"Binary file skipped: {file_path}"

        content = base64.b64decode(
            data["content"]
        ).decode("utf-8", errors="ignore")

        # Limit karo — token save karo
        if len(content) > 3000:
            content = content[:3000] + "\n...[truncated]"

        return f"File: {file_path}\n\n{content}"

    except Exception as e:
        return f"Error reading file: {str(e)}"

# Search file by name in GitHub repo
@tool
def search_file (repo_full_name: str, query: str) -> str:
    """
    Search files by name in GitHub repo.
    Use for finding specific files like auth, db, api, config.
    repo_full_name format: 'owner/repo'
    query: 'auth', 'database', 'middleware', 'route'
    """
    try:
        url = "https://api.github.com/search/code"
        params = {
            "q": f"repo:{repo_full_name} filename:{query}",
            "per_page": 10
        }
        res = requests.get(url, headers=HEADERS, params=params)

        if not res.ok:
            return f"Search failed: {res.status_code}"

        items = res.json().get("items", [])

        if not items:
            return f"No files found for: {query}"

        output = [f"📄 {item['path']}" for item in items]
        return "\n".join(output)

    except Exception as e:
        return f"Error searching file: {str(e)}"

# Search code inside files in GitHub repo
@tool
def search_code (repo_full_name: str, query: str) -> str:
    """
    Search for exact keyword or pattern inside code files.
    Use for finding specific functions, variables, imports.
    repo_full_name format: 'owner/repo'
    query: 'JWT', 'useState', 'db.connect', 'getUserById'
    """
    try:
        url = "https://api.github.com/search/code"
        params = {
            "q": f"repo:{repo_full_name} {query}",
            "per_page": 10
        }
        res = requests.get(url, headers=HEADERS, params=params)

        if not res.ok:
            return f"Search failed: {res.status_code}"

        items = res.json().get("items", [])

        if not items:
            return f"No code found for: {query}"

        output = [f"📄 {item['path']}" for item in items]
        return "\n".join(output)

    except Exception as e:
        return f"Error searching code: {str(e)}"