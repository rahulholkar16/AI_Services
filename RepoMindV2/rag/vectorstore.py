from langchain_pinecone import PineconeVectorStore;
from pinecone import Pinecone, ServerlessSpec;
from .embeddings import get_embeddings;
import os;
import time;

INDEX_NAME = "github-repo";
_vector_store = None;

def _get_pinecone_client() -> Pinecone:
    return Pinecone(api_key=os.getenv("PINECONE_API_KEY"));

def __ensure_index_exists (): 
    pc = _get_pinecone_client();
    existing = [i.name for i in pc.list_indexes()]
    if INDEX_NAME not in existing:
        pc.create_index(
            name=INDEX_NAME,
            dimension=1024,
            metric="cosine",
            spec=ServerlessSpec(
                cloud="aws",
                region="us-east-1"
            )
        )

        while not pc.describe_index(INDEX_NAME).status["ready"]:
            time.sleep(2)
        print("Index ready!")
    else:
        print(f"Index exists: {INDEX_NAME}");

def get_vector_store() -> PineconeVectorStore:
    global _vector_store;
    if _vector_store is None:
        __ensure_index_exists();
        _vector_store = PineconeVectorStore(
            index_name=INDEX_NAME,
            embedding=get_embeddings(),
            pinecone_api_key=os.getenv("PINECONE_API_KEY")
        );
    return _vector_store;