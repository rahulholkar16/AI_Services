from app.github.repo_service import clone_repo;
CURRENT_REPO_PATH = None

def set_repository(repo_url: str):
    global CURRENT_REPO_PATH
    repo_path = clone_repo(repo_url)
    CURRENT_REPO_PATH = repo_path 

def get_repository():
    return CURRENT_REPO_PATH