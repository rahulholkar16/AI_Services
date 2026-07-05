# from langchain_google_genai import GoogleGenerativeAIEmbeddings
import os

_embeddings = None

# def get_embeddings():
#     global _embeddings
#     if _embeddings is None:
#         _embeddings = GoogleGenerativeAIEmbeddings(
#             model="gemini-embedding-2-preview",
#             google_api_key=os.getenv("GOOGLE_API_KEY")
#         )
#     return _embeddings;

from langchain_huggingface import HuggingFaceEmbeddings

def get_embeddings():
    global _embeddings
    if _embeddings is None:
        print("Loading local embedding model...")
        _embeddings = HuggingFaceEmbeddings(
            model_name="BAAI/bge-small-en-v1.5",
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True}
        )
        print("Model loaded!")
    return _embeddings