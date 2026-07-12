import requests
import base64
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from app.tools.files_tool import get_default_branch, HEADERS

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

MAX_FILE_SIZE = 50000


def get_repo_files(repo_full_name: str) -> list[str]:
    branch = get_default_branch(repo_full_name)
    url = f"https://api.github.com/repos/{repo_full_name}/git/trees/{branch}?recursive=1"  # ✅ /HEAD hataya
    res = requests.get(url, headers=HEADERS) 

    if not res.ok:
        raise ValueError(f"Failed to fetch tree: {res.status_code}")

    tree = res.json().get("tree", [])
    files = []

    for item in tree:
        path = item["path"]

        if any(part in IGNORE_DIRS for part in path.split("/")):
            continue

        if item["type"] != "blob":
            continue

        ext = "." + path.split(".")[-1].lower() if "." in path else ""
        if ext not in ALLOW_EXTENSIONS:
            continue

        if item.get("size", 0) > MAX_FILE_SIZE:
            continue

        files.append(path)

    return files


def fetch_file_content(repo_full_name: str, file_path: str) -> str | None:
    url = f"https://api.github.com/repos/{repo_full_name}/contents/{file_path}"
    res = requests.get(url, headers=HEADERS)  # ✅ Token wala HEADERS

    if not res.ok:
        return None

    data = res.json()
    try:
        content = base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
        return content if content.strip() else None
    except Exception:
        return None


def load_repo_documents(repo_full_name: str) -> list[Document]:
    files = get_repo_files(repo_full_name)
    docs = []

    print(f"Found {len(files)} files to index...")

    for path in files:
        content = fetch_file_content(repo_full_name, path)
        if not content:
            continue

        docs.append(Document(
            page_content=content,
            metadata={
                "source": path,
                "repo_full_name": repo_full_name,
                "extension": "." + path.split(".")[-1].lower()
            }
        ))

    print(f"Loaded {len(docs)} documents")
    return docs


def chunk_documents(docs: list[Document]) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100,
        length_function=len,
    )

    chunks = splitter.split_documents(docs)
    print(f"Created {len(chunks)} chunks")
    return chunks