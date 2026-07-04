def extract_full_name(repo_url: str) -> str:
    parts = repo_url.rstrip("/").split("github.com/")
    if len(parts) < 2:
        raise ValueError(f"Invalid GitHub URL: {repo_url}")
    return parts[1].replace(".git", "")

print(extract_full_name("https://github.com/rahulholkar16/Code-Master.git"))