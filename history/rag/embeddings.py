# app/rag/embeddings.py
from langchain_google_genai import GoogleGenerativeAIEmbeddings
import os

_embeddings = None

def get_embeddings():
    global _embeddings
    if _embeddings is None:
        _embeddings = GoogleGenerativeAIEmbeddings(
            model="gemini-embedding-2-preview",
            google_api_key=os.getenv("GOOGLE_API_KEY")
        )
    return _embeddings