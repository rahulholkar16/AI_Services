def extract_full_name(repo_url: str) -> str:
    parts = repo_url.rstrip("/").split("github.com/")
    print(parts)

    if len(parts) < 2:
        raise ValueError(f"Invalid GitHub URL: {repo_url}")
    return parts[1].replace(".git", "")
