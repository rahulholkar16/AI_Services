from fastapi import APIRouter, HTTPException;
from pydantic import BaseModel;
from app.rag import get_vector_store, load_repo_documents, chunk_documents;
from app.utils.Repo_Full_Name_Extracter import extract_full_name;

router = APIRouter(
    prefix="/api/repo",
    tags=["repo"],
    responses={404: {"description": "Not found"}},
);

class IndexRequest(BaseModel):
    repo_url: str;

@router.post("/index")
async def index_repo(request: IndexRequest):
    """
    Index a GitHub repository for semantic search.
    This will fetch all files, chunk them, and store embeddings in Pinecone.
    """
    try:
        repo_full_name = extract_full_name(request.repo_url);
        docs = load_repo_documents(repo_full_name);
        if not docs:
            raise HTTPException(status_code=404, detail="No documents found in the repository.");

        chunks = chunk_documents(docs);
        if not chunks:
            raise HTTPException(status_code=500, detail="Failed to chunk documents.");

        vector_store = get_vector_store();
        batch_size = 50
        total = len(chunks)

        for i in range(0, total, batch_size):
            batch = chunks[i:i + batch_size]
            vector_store.add_documents(batch)
            print(f"Indexed {min(i + batch_size, total)}/{total} chunks")

        return {"message": f"Indexed {len(chunks)} chunks from {request.repo_full_name}."};
    except HTTPException:
        raise           
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e));
