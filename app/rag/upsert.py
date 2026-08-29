import uuid
from langchain_core.documents import Document
from .embeddings import get_embeddings

MAX_METADATA_TEXT = 39000

async def embed_and_build_vectors(chunks: list[Document]) -> list[dict]:
    embeddings = get_embeddings()
    texts = [c.page_content for c in chunks]
    vectors = await embeddings.aembed_documents(texts)

    return [
        {
            "id": str(uuid.uuid4()),
            "values": vector,
            "metadata": {
                **chunk.metadata,
                "text": chunk.page_content[:MAX_METADATA_TEXT],
            },
        }
        for chunk, vector in zip(chunks, vectors)
    ]
