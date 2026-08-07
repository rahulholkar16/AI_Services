from langchain_core.prompts import ChatPromptTemplate
from app.prompt.prompt import ARCHITECTURE_PROMPT
from pathlib import Path
from app.services.llm import llm
from app.schemas.tech_stack import ArchitectureReport

prompt = ChatPromptTemplate.from_template(ARCHITECTURE_PROMPT)

structured_llm = llm.with_structured_output(ArchitectureReport)

IGNORE_DIRS = {".git", "node_modules", ".next", "dist", "build", "__pycache__", ".venv"}

def build_architecture_context(repo_path: str) -> str:
    repo = Path(repo_path)
    context = ""
    total_chars = 0
    MAX_TOTAL_CHARS = 4000  # ✅ Hard limit — 4000 chars total

    # Priority files pehle
    priority_files = [
        "README.md",
        "package.json",
        "schema.prisma",
        "middleware.ts",
        "middleware.js",
    ]

    # Pattern wali files
    pattern_files = [
        "*auth*", "*route*", "*action*", "*service*"
    ]

    seen = set()
    all_files = []

    # Priority files pehle add karo
    for name in priority_files:
        for f in repo.rglob(name):
            if not any(part in IGNORE_DIRS for part in f.parts):
                all_files.append(f)

    # Pattern files baad mein
    for pattern in pattern_files:
        for f in repo.rglob(pattern):
            if not any(part in IGNORE_DIRS for part in f.parts):
                all_files.append(f)

    for file in all_files:
        if file in seen:
            continue
        seen.add(file)

        # Total limit hit ho gayi?
        if total_chars >= MAX_TOTAL_CHARS:
            break

        try:
            content = file.read_text(encoding="utf-8", errors="ignore")

            # Per file limit
            remaining = MAX_TOTAL_CHARS - total_chars
            snippet = content[:min(500, remaining)]  # ✅ 500 chars per file

            if not snippet.strip():
                continue

            entry = f"FILE: {file.relative_to(repo)}\n{snippet}\n=======================\n"
            context += entry
            total_chars += len(entry)

        except Exception:
            continue

    return context or "No context available."


def analyze_architecture(repo_path: str):
    context = build_architecture_context(repo_path)
    chain = prompt | structured_llm
    return chain.invoke({"context": context})