from langchain_core.prompts import ChatPromptTemplate
from app.prompt.prompt import ARCHITECTURE_PROMPT;
from pathlib import Path;
from app.services.llm import llm;
from app.schemas.tech_stack import ArchitectureReport;

prompt = ChatPromptTemplate.from_template(
    ARCHITECTURE_PROMPT
)

structured_llm = llm.with_structured_output(
    ArchitectureReport
)

def build_architecture_context(repo_path):
    context = ""
    repo = Path(repo_path);
    files = []
    patterns = [
        "README.md",
        "package.json",
        "schema.prisma",
        "middleware.ts",
        "middleware.js",
        "*auth*",
        "*route*",
        "*action*",
        "*service*",
    ]
    for pattern in patterns:
        files.extend(repo.rglob(pattern))

    for file in files:
        try:
            content = file.read_text(encoding="utf-8", errors="ignore");
            context += f"""
                            FILE: {file}
                            
                            {content[:5000]}

                        =======================
                        """
        except:
            pass

    return context;


def analyze_architecture(repo_path):

    context = build_architecture_context(
        repo_path
    )

    chain = prompt | structured_llm

    result = chain.invoke({
        "context": context
    })

    return result