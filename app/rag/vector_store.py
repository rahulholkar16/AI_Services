from langchain_chroma import Chroma;
from app.rag.embeddings import get_embeddings;

CHROMA_DIR = "./chroma_db"
COLLECTION_NAME = "github_repo"

_vector_store = None

def get_vector_store() -> Chroma:
    global _vector_store

    if _vector_store is None:
        _vector_store = Chroma(
            collection_name=COLLECTION_NAME,
            embedding_function=get_embeddings(),
            persist_directory=CHROMA_DIR,
        )
    return _vector_store

def index_chunks(chunks: list, force: bool = False) -> int:
    store = get_vector_store()
    existing = store._collection.count()

    if existing > 0 and not force:
        print(f"Already indexed: {existing} chunks — skipping")
        return existing

    if force and existing > 0:
        print(f"Clearing {existing} old chunks...")
        store.reset_collection()

    batch_size = 50
    total = len(chunks)
    for i in range(0, total, batch_size):
        batch = chunks[i:i + batch_size]
        store.add_documents(batch)
        print(f"Indexed {min(i + batch_size, total)}/{total} chunks")

    print(f"Done! Total indexed: {total}")
    return total