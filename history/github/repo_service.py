from git import Repo;
from pathlib import Path;

REPOS_DIR = Path("data/repos");

def clone_repo(repo_url: str):
    REPOS_DIR.mkdir(parents=True, exist_ok=True);
    repo_name = repo_url.split("/")[-1];
    repo_path = REPOS_DIR / repo_name;
    if repo_path.exists():
        return str(repo_path);
    
    Repo.clone_from(repo_url, repo_path);
    return str(repo_path);