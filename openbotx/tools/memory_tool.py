from __future__ import annotations

from typing import Any

from openbotx.agent.memory import MemoryStore
from openbotx.tools.base import Tool


class SaveMemoryTool(Tool):
    """Save conversation history and updated memory."""

    name = "save_memory"
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
