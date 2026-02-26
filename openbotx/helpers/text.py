def humanize(name: str) -> str:
    """Convert an identifier like 'web_search' to 'Web Search'."""
    return name.replace("_", " ").replace("-", " ").title()


def describe_tool_use(name: str, arguments: dict) -> str:
    """Return a short phrase describing what a tool call is doing."""
    args = arguments or {}
    match name:
        case "read_file":
            return f"Reading {args.get('path', '')}"
        case "write_file":
            return f"Writing {args.get('path', '')}"
        case "edit_file":
            return f"Editing {args.get('path', '')}"
        case "list_dir":
            return f"Listing {args.get('path', '.')}"
        case "web_search":
            return f"Searching for {args.get('query', '')}"
        case "web_fetch":
            return f"Fetching {args.get('url', '')}"
        case "exec":
            return f"Running {args.get('command', '')}"
        case "http_client":
            method = args.get("method", "GET").upper()
            return f"{method} {args.get('url', '')}"
        case "browser":
            action = args.get("action", "")
            if action == "navigate":
                return f"Navigating to {args.get('url', '')}"
            return f"Browser {action}"
        case "spawn":
            return f"Spawning {args.get('label') or args.get('task', '')}"
        case "message":
            return "Sending message"
        case "cron":
            return f"Cron {args.get('action', '')}"
        case "save_memory":
            return "Saving memory"
        case "generate_image":
            return "Generating image"
        case _:
            return humanize(name)
