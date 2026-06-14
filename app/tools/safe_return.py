def safe_return(result) -> str:
    if not result:
        return "No results found."
    if isinstance(result, list):
        return "\n".join(str(r) for r in result) if result else "No results found."
    return str(result).strip() or "No results found."