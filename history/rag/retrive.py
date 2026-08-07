from app.rag.vector_store import get_vector_store;

IMPORTANT_FILES = [
    "package.json",
    "prisma/schema.prisma",
    "README.md",
    ".env.example",
]

def search_repo(query: str):
    vector_store = get_vector_store()

    results = vector_store.max_marginal_relevance_search(
        query,
        k=10,
        fetch_k=25
    )

    important_docs = []

    for file in IMPORTANT_FILES:
        docs = vector_store.similarity_search(
            query="nextjs",
            k=1,
            filter={
                "file_name": file
            }
        )

        if docs:
            important_docs.extend(docs)

    for doc in results:
        print(doc.metadata["source"]);
    
    for doc in important_docs:
        print(doc.metadata["source"]); 

    return important_docs + results