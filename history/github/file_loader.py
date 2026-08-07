from pathlib import Path
from langchain_core.documents import Document

ALLOWED_EXTENSIONS = {
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".py",
    ".md",
    ".yml",
    ".json",
    ".toml",
    ".prisma",
}

SPECIAL_FILES = {
    "package.json",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    ".env",
    ".env.example",
    "README.md",
    "pnpm-lock.yaml",
    "bun.lock",
}

def get_special_docs(all_docs):
    special = []

    for doc in all_docs:
        if (
            doc.metadata["is_package"]
            or doc.metadata["is_schema"]
            or doc.metadata["is_readme"]
        ):
            special.append(doc)

    return special


def get_file_type(file: Path) -> str:
    if file.name == "package.json":
        return "package"

    if file.name == "schema.prisma":
        return "schema"

    if file.name.lower() == "readme.md":
        return "readme"

    return "source_code"


def load_repo(repo_path: str) -> list[Document]:
    documents = []

    repo = Path(repo_path)

    for file in repo.rglob("*"):

        if not file.is_file():
            continue

        if file.suffix not in ALLOWED_EXTENSIONS:
            continue

        try:
            content = file.read_text(
                encoding="utf-8",
                errors="ignore"
            )

            if not content.strip():
                continue

            documents.append(
                Document(
                    page_content=content,
                    metadata={
                        "source": str(file),
                        "file_name": file.name,
                        "extension": file.suffix,
                        "directory": str(file.parent),
                        "type": get_file_type(file),

                        "is_package": file.name == "package.json",
                        "is_schema": file.name == "schema.prisma",
                        "is_readme": file.name.lower() == "readme.md",
                    },
                )
            )

        except Exception as e:
            print(f"Error reading {file}: {e}")

    print(f"Loaded {documents[0]} documents")

    return documents