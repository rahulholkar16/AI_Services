# app/rag/vectorstore.py
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec
from app.rag.embeddings import get_embeddings
import os
import time

INDEX_NAME = "github-repo"
_vector_store = None

def _get_pinecone_client() -> Pinecone:
    return Pinecone(api_key=os.getenv("PINECONE_API_KEY"))


def _ensure_index_exists():
    """Index exist nahi karta toh banao."""
    pc = _get_pinecone_client()
    existing = [i.name for i in pc.list_indexes()]

    if INDEX_NAME not in existing:
        print(f"Creating Pinecone index: {INDEX_NAME}")
        pc.create_index(
            name=INDEX_NAME,
            dimension=1024,  # voyage-code-3 dimension
            metric="cosine",
            spec=ServerlessSpec(
                cloud="aws",
                region="us-east-1"
            )
        )
        # Index ready hone ka wait karo
        while not pc.describe_index(INDEX_NAME).status["ready"]:
            print("Waiting for index to be ready...")
            time.sleep(2)

        print("Index created and ready!")
    else:
        print(f"Index already exists: {INDEX_NAME}")


def get_vector_store() -> PineconeVectorStore:
    global _vector_store
    if _vector_store is None:
        _ensure_index_exists()
        _vector_store = PineconeVectorStore(
            index_name=INDEX_NAME,
            embedding=get_embeddings(),
            pinecone_api_key=os.getenv("PINECONE_API_KEY")
        )
    return _vector_store


def index_chunks(chunks: list, force: bool = False) -> int:
    """Chunks Pinecone mein index karo."""
    store = get_vector_store()
    pc = _get_pinecone_client()
    index = pc.Index(INDEX_NAME)

    # Existing chunks count karo
    stats = index.describe_index_stats()
    existing = stats.get("total_vector_count", 0)

    if existing > 0 and not force:
        print(f"Already indexed: {existing} chunks — skipping")
        return existing

    if force and existing > 0:
        print(f"Clearing {existing} old chunks...")
        index.delete(delete_all=True)
        time.sleep(2)  # Delete hone ka wait karo
        print("Old chunks cleared!")

    # Batch mein add karo
    batch_size = 50
    total = len(chunks)

    for i in range(0, total, batch_size):
        batch = chunks[i:i + batch_size]
        store.add_documents(batch)
        print(f"Indexed {min(i + batch_size, total)}/{total} chunks")

    print(f"Done! Total indexed: {total}")
    return total