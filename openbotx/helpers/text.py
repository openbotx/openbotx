def humanize(name: str) -> str:
    """Convert an identifier like 'web_search' to 'Web Search'."""
    return name.replace("_", " ").replace("-", " ").title()
