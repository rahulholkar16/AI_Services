import requests;
from langchain.tools import tool;

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
    ".json", ".md", ".yaml", ".yml", ".tomal",
    ".css", ".html", ".sh", ".go", ".rs",
    ".java", ".c", ".cpp", ".c++", ".h", ".prisma"
}

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

        # Base64 decode karo
        import base64
        content = base64.b64decode(
            data["content"]
        ).decode("utf-8", errors="ignore")

        # Limit karo — token save karo
        if len(content) > 3000:
            content = content[:3000] + "\n...[truncated]"

        return f"File: {file_path}\n\n{content}"

    except Exception as e:
        return f"Error reading file: {str(e)}"