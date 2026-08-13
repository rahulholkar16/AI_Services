import requests;
import time;
import logging;
from fastapi import APIRouter, HTTPException, Request;
from pydantic import BaseModel;
from app.rag import get_vector_store, load_repo_documents, chunk_documents;
from app.utils.Repo_Full_Name_Extracter import extract_full_name;
from app.tools.files_tool import HEADERS, get_default_branch, IGNORE_DIRS, ALLOW_EXTENSIONS;
from app.middleware.rate_limit import limiter

router = APIRouter(
    prefix="/api/repo",
    tags=["repo"],
    responses={404: {"description": "Not found"}},
);
logger = logging.getLogger(__name__)

class IndexRequest(BaseModel):
    repo_url: str;
    force: bool = False;

class TreeRequest(BaseModel):
    repo_url: str;


@router.post("/index")
@limiter.limit("10/hour")
async def index_repo(request: Request, body: IndexRequest):
    try:
        repo_full_name = extract_full_name(body.repo_url)

        vector_store = get_vector_store()
        index = vector_store._index

        # Check if namespace already exists
        stats = index.describe_index_stats()
        already_indexed = repo_full_name in stats.get("namespaces", {})

        if already_indexed and not body.force:
            return {
                "message": "Repository already indexed.",
                "repo_full_name": repo_full_name,
                "already_indexed": True,
            }

        if already_indexed and body.force:
            index.delete(delete_all=True, namespace=repo_full_name)
            logger.info("Cleared stale index for %s, re-indexing...", repo_full_name)

        docs = load_repo_documents(repo_full_name)

        if not docs:
            raise HTTPException(
                status_code=404,
                detail="No documents found in the repository."
            )

        chunks = chunk_documents(docs)

        if not chunks:
            raise HTTPException(
                status_code=500,
                detail="Failed to chunk documents."
            )

        batch_size = 5
        total = len(chunks)

        for i in range(0, total, batch_size):
            batch = chunks[i:i + batch_size]

            for attempt in range(4):
                try:
                    vector_store.add_documents(
                        documents=batch,
                        namespace=repo_full_name,
                    )
                    break

                except Exception as e:
                    if "RESOURCE_EXHAUSTED" in str(e) and attempt < 3:
                        wait = 15 * (attempt + 1)
                        logger.warning(
                            "Rate limited on batch %s-%s. Retrying in %s seconds...",
                            i, min(i + batch_size, total), wait,
                        )
                        time.sleep(wait)
                    else:
                        raise

            logger.info("Indexed %s/%s chunks", min(i + batch_size, total), total)
            time.sleep(6)
        return {
            "message": f"Indexed {total} chunks from {repo_full_name}.",
            "repo_full_name": repo_full_name,
            "already_indexed": False,
            "total_chunks": total,
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _build_file_tree(paths: list[str]) -> list[dict]:
    root: dict = {}

    for path in paths:
        parts = path.split("/")
        node = root
        for i, part in enumerate(parts):
            is_file = i == len(parts) - 1
            if part not in node:
                node[part] = {"__meta__": {"is_file": is_file}, "__children__": {}}
            elif is_file:
                node[part]["__meta__"]["is_file"] = True
            node = node[part]["__children__"]

    def to_list(children: dict) -> list[dict]:
        items = []
        for name, value in children.items():
            is_file = value["__meta__"]["is_file"]
            if is_file:
                ext = name.split(".")[-1] if "." in name else ""
                items.append({"name": name, "type": "file", "ext": ext})
            else:
                items.append({
                    "name": name,
                    "type": "dir",
                    "children": to_list(value["__children__"]),
                })
        items.sort(key=lambda n: (n["type"] != "dir", n["name"].lower()))
        return items

    return to_list(root)

@router.post("/tree")
async def get_repo_tree(request: TreeRequest):
    """
    Get the file/folder structure of a GitHub repo as a nested JSON tree.
    Used by the frontend's FileTree panel.
    """
    try:
        repo_full_name = extract_full_name(request.repo_url)
        branch = get_default_branch(repo_full_name)

        url = f"https://api.github.com/repos/{repo_full_name}/git/trees/{branch}?recursive=1"
        res = requests.get(url, headers=HEADERS)

        if not res.ok:
            raise HTTPException(status_code=res.status_code, detail="Failed to fetch repository tree")

        tree_items = res.json().get("tree", [])

        paths = []
        for item in tree_items:
            path = item["path"]
            if any(part in IGNORE_DIRS for part in path.split("/")):
                continue
            if item["type"] != "blob":
                continue
            if item["type"] == "blob":
                ext = "." + path.split(".")[-1].lower() if "." in path else ""
                if ext not in ALLOW_EXTENSIONS:
                    continue
            paths.append(path)

        file_tree = _build_file_tree(paths[:400])
        return {"repo_full_name": repo_full_name, "tree": file_tree}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/info")
async def get_repo_info(request: TreeRequest):
    """
    Get basic GitHub repo metadata (owner, name, language, stars, description).
    Used by the frontend to populate the repo info card.
    """
    try:
        repo_full_name = extract_full_name(request.repo_url)
        res = requests.get(
            f"https://api.github.com/repos/{repo_full_name}",
            headers=HEADERS,
        )
        if not res.ok:
            raise HTTPException(status_code=res.status_code, detail="Repository not found")

        data = res.json()
        owner, name = repo_full_name.split("/")

        return {
            "owner": owner,
            "name": name,
            "language": data.get("language") or "Unknown",
            "stars": data.get("stargazers_count", 0),
            "description": data.get("description") or "",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
