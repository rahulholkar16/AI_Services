from app.analyzers.tech_stack import tech_stack_context;
from app.schemas.tech_stack import TechStack;
from app.services.llm import llm;
from app.prompt.prompt import tech_stack_prompt;
from fastapi import APIRouter;
from app.github.repo_service import clone_repo;
from app.schemas.repo import RepoRequest;
from app.analyzers.architecture import analyze_architecture;

router = APIRouter();

@router.post("/tech_stack")
async def techStack (data: RepoRequest):
    structured_llm = llm.with_structured_output(TechStack);
    repo_path = clone_repo(data.repo_url);
    context = tech_stack_context(repo_path);
    print(context)
    prompt = tech_stack_prompt(context);
    answer = structured_llm.invoke(prompt);
    return {"answer": answer};

@router.post("/repository/architecture")
def architecture(data: RepoRequest):

    repo_path = clone_repo(data.repo_url)

    result = analyze_architecture(repo_path)

    return result.model_dump()