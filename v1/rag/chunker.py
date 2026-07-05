from langchain_text_splitters import RecursiveCharacterTextSplitter;

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1200,
    chunk_overlap=150
);

IMPORTANT_FILES = {
    "package.json",
    "schema.prisma",
    "README.md",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    ".env.example",
}

def split_document(documents):
    final_docs = []

    for doc in documents:
        file_name = doc.metadata.get("file_name")

        if file_name in IMPORTANT_FILES:
            final_docs.append(doc)
            continue

        chunks = text_splitter.split_documents([doc])
        final_docs.extend(chunks)
    return final_docs;
