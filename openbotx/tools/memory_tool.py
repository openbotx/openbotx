from typing import Any

from openbotx.agent.memory import MemoryStore
from openbotx.tools.base import Tool


class MemorySaveTool(Tool):
    """Save conversation history and updated memory."""

    name = "memory_save"
    description = (
        "Save a conversation summary to HISTORY.md and update long-term memory "
        "in MEMORY.md. Used during memory consolidation."
    )
    parameters = {
        "type": "object",
        "properties": {
            "history_entry": {
                "type": "string",
                "description": "Summary of recent conversation for HISTORY.md",
            },
            "updated_memory": {
                "type": "string",
                "description": "Updated long-term memory content for MEMORY.md",
            },
        },
        "required": ["history_entry", "updated_memory"],
    }

    def __init__(self, memory_store: MemoryStore):
        self._memory = memory_store

    async def execute(
        self,
        history_entry: str,
        updated_memory: str,
        **kwargs: Any,
    ) -> str:
        try:
            history_path = self._memory.workspace / "memory" / "HISTORY.md"
            history_path.parent.mkdir(parents=True, exist_ok=True)
            with open(history_path, "a", encoding="utf-8") as f:
                f.write(history_entry + "\n\n")

            memory_path = self._memory.workspace / "memory" / "MEMORY.md"
            memory_path.write_text(updated_memory, encoding="utf-8")

            return "Memory saved successfully."
        except Exception as e:
            return f"Error saving memory: {e}"


class MemoryReadTool(Tool):
    """Read memory files."""

    name = "memory_read"
    description = (
        "Read memory files. Returns MEMORY.md (long-term facts) or "
        "HISTORY.md (conversation summaries)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "file": {
                "type": "string",
                "enum": ["memory", "history"],
                "description": "Which file to read: 'memory' for MEMORY.md, 'history' for HISTORY.md",
            },
            "max_lines": {
                "type": "integer",
                "description": "Max lines to return from the end (default: all). Useful for HISTORY.md.",
            },
        },
        "required": ["file"],
    }

    def __init__(self, memory_store: MemoryStore):
        self._memory = memory_store

    async def execute(self, file: str, max_lines: int | None = None, **kwargs: Any) -> str:
        filename = "MEMORY.md" if file == "memory" else "HISTORY.md"
        path = self._memory.workspace / "memory" / filename

        if not path.exists():
            return f"{filename} does not exist yet."

        try:
            text = path.read_text(encoding="utf-8")
        except Exception as e:
            return f"Error reading {filename}: {e}"

        if not text.strip():
            return f"{filename} is empty."

        if max_lines is not None and max_lines > 0:
            lines = text.splitlines()
            if len(lines) > max_lines:
                lines = lines[-max_lines:]
                text = "\n".join(lines)

        return text


class MemorySearchTool(Tool):
    """Search across memory and history files."""

    name = "memory_search"
    description = "Search across memory and history files for specific information."
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search term (case-insensitive substring match)",
            },
        },
        "required": ["query"],
    }

    def __init__(self, memory_store: MemoryStore):
        self._memory = memory_store

    async def execute(self, query: str, **kwargs: Any) -> str:
        results: list[str] = []
        query_lower = query.lower()

        for filename in ("MEMORY.md", "HISTORY.md"):
            path = self._memory.workspace / "memory" / filename
            if not path.exists():
                continue

            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except Exception:
                continue

            for i, line in enumerate(lines):
                if query_lower in line.lower():
                    context_lines = []
                    if i > 0:
                        context_lines.append(lines[i - 1])
                    context_lines.append(line)
                    if i < len(lines) - 1:
                        context_lines.append(lines[i + 1])
                    results.append(f"[{filename}:{i + 1}]\n" + "\n".join(context_lines))

        if not results:
            return f"No matches found for '{query}'."

        return "\n\n".join(results)
