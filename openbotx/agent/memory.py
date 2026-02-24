import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MEMORY_FILE = "MEMORY.md"
HISTORY_FILE = "HISTORY.md"


class MemoryStore:

    def __init__(self, workspace: Path):
        self._workspace = workspace
        self._memory_dir = workspace / "memory"
        self._memory_dir.mkdir(parents=True, exist_ok=True)

    @property
    def workspace(self) -> Path:
        return self._workspace

    def get_memory_context(self) -> str:
        memory_path = self._memory_dir / MEMORY_FILE
        if not memory_path.exists():
            return ""
        try:
            content = memory_path.read_text(encoding="utf-8").strip()
            return content
        except Exception as e:
            logger.warning("failed to read memory file: %s", e)
            return ""

    def get_consolidation_messages(
        self, session: Any, window: int
    ) -> list[dict[str, Any]]:
        start = session.last_consolidated
        end = len(session.messages)
        if end - start < window:
            return []

        unconsolidated = session.messages[start:end]
        current_memory = self.get_memory_context()

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a memory consolidation agent. "
                    "Analyze the conversation below and:\n"
                    "1. Write a timestamped summary for HISTORY.md\n"
                    "2. Update the long-term MEMORY.md with important facts, "
                    "preferences, and context about the user.\n\n"
                    "Current MEMORY.md content:\n"
                    f"{current_memory or '(empty)'}\n\n"
                    "Use the save_memory tool to persist both."
                ),
            }
        ]

        for msg in unconsolidated:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

        return messages

    def mark_consolidated(self, session: Any, count: int) -> None:
        session.last_consolidated = count
