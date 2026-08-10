from fastapi import APIRouter;
from app.schemas.repo import RepoRequest;
from app.github.repo_service import clone_repo;
from app.github.file_loader import load_repo, ALLOWED_EXTENSIONS, SPECIAL_FILES;
from app.rag.chunker import split_document;
from app.rag.vector_store import index_chunks;
from pathlib import Path;

router = APIRouter(prefix="/repositiory", tags=["Repository"]);

def get_directory_tree(path: Path, max_depth=3, current_depth=0):
    if current_depth > max_depth:
        return None
    
    name = path.name
    if name.startswith(".") or name in ("node_modules", "__pycache__", "venv", ".venv", "dist", "build", "target"):
        return None
        
    if path.is_dir():
        children = []
        try:
            for child in sorted(path.iterdir()):
                child_node = get_directory_tree(child, max_depth, current_depth + 1)
                if child_node:
                    children.append(child_node)
        except Exception:
            pass
        return {"name": name, "type": "dir", "children": children}
    else:
        if path.suffix in ALLOWED_EXTENSIONS or name in SPECIAL_FILES:
            return {"name": name, "type": "file", "ext": path.suffix.replace(".", "")}
        return None

@router.post("/clone")
async def clone (data: RepoRequest):
    path = clone_repo(data.repo_url);
    return {
        "success": True,
        "path": path
    }

@router.post("/load")
async def load (data: RepoRequest):
    repo_path = clone_repo(data.repo_url);
    documents = load_repo(repo_path);
    return {
        "total_document": len(documents)
    }

@router.post("/index")
async def index_repo(data: RepoRequest):
    repo_path = clone_repo(data.repo_url);
    documents = load_repo(repo_path);

    chunks = split_document(documents);
    totalVectors = index_chunks(chunks)

    return {
        "indexed_chunks": totalVectors
    }

@router.post("/tree")
def get_tree(data: RepoRequest):
    repo_path = clone_repo(data.repo_url)
    tree = get_directory_tree(Path(repo_path))
    # Return children of the root to match frontend format
    if tree and "children" in tree:
        return {"tree": tree["children"]}
    return {"tree": []}
