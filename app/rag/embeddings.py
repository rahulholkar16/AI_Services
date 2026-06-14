from langchain_voyageai import VoyageAIEmbeddings
import os

_embeddings = None

def get_embeddings():
    global _embeddings
    if _embeddings is None:
        _embeddings = VoyageAIEmbeddings(
            model="voyage-code-3",  # ✅ Best for code, no download
            voyage_api_key=os.getenv("VOYAGE_API_KEY")
        )
    return _embeddings