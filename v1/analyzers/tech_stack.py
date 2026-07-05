from pathlib import Path

IMPORTANT_FILES = [
    "package.json",
    "README.md",
    "schema.prisma",
    ".env.example",
    "docker-compose.yml",
    "Dockerfile",
]

def tech_stack_context (repo_path: str) -> str:
    context_parts = [];
    for file_name in IMPORTANT_FILES:
        file_path = Path(repo_path) / file_name

        if file_path.exists():
            try:
                content = file_path.read_text(
                    encoding="utf-8",
                    errors="ignore"
                )

                context_parts.append(
                    f"\n\n=== {file_name} ===\n{content[:5000]}"
                )

            except Exception:
                pass

    return "\n".join(context_parts)