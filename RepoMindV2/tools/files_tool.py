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
    

