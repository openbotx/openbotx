import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from openbotx.agent.memory import MemoryStore
from openbotx.agent.skills import SkillsLoader

logger = logging.getLogger(__name__)

BOOTSTRAP_FILES = ["AGENTS.md", "SOUL.md", "USER.md", "TOOLS.md"]

IDENTITY = "You are OpenBotX, a personal AI assistant."


class ContextBuilder:
    def __init__(
        self,
        workspace: Path,
        memory: MemoryStore,
        skills_loader: SkillsLoader,
        public_url: str = "",
    ):
        self._workspace = workspace
        self._memory = memory
        self._skills_loader = skills_loader
        self._public_url = public_url

    def build_system_prompt(self) -> str:
        parts = [IDENTITY]

        now = datetime.now()
        parts.append(f"\nCurrent date and time: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}.")

        if self._public_url:
            parts.append(f"\nPublic URL: {self._public_url}")

        for filename in BOOTSTRAP_FILES:
            filepath = self._workspace / filename
            if filepath.exists():
                try:
                    content = filepath.read_text(encoding="utf-8").strip()
                    if content:
                        parts.append(f"\n# {filename}\n{content}")
                except Exception as e:
                    logger.warning("failed to read bootstrap file %s: %s", filename, e)

        memory_context = self._memory.get_memory_context()
        if memory_context:
            parts.append(f"\n# Memory\n{memory_context}")

        for skill_name, skill_content in self._skills_loader.get_always_skills():
            parts.append(f"\n# Skill: {skill_name}\n{skill_content}")

        skills_summary = self._skills_loader.build_skills_summary()
        if skills_summary:
            parts.append(f"\n# Available Skills\n{skills_summary}")

        return "\n".join(parts)

    @staticmethod
    def build_messages(
        system_prompt: str,
        history: list[dict[str, Any]],
        user_content: str,
        media: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
        ]

        messages.extend(history)

        if media:
            content_parts: list[dict[str, Any]] = [{"type": "text", "text": user_content}]
            for item in media:
                content_parts.append(
                    {
                        "type": "image",
                        "url": item,
                    }
                )
            messages.append({"role": "user", "content": content_parts})
        else:
            messages.append({"role": "user", "content": user_content})

        return messages

    @staticmethod
    def add_tool_result(
        messages: list[dict[str, Any]],
        tool_call_id: str,
        tool_name: str,
        result: str,
    ) -> None:
        truncated = result[:500] if len(result) > 500 else result
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "name": tool_name,
                "content": truncated,
            }
        )

    @staticmethod
    def add_assistant_message(
        messages: list[dict[str, Any]],
        content: str | None,
        tool_calls: list[dict[str, Any]] | None = None,
        reasoning_content: str | None = None,
    ) -> None:
        msg: dict[str, Any] = {
            "role": "assistant",
            "content": content or "",
        }
        if tool_calls:
            msg["tool_calls"] = tool_calls
        if reasoning_content:
            msg["reasoning_content"] = reasoning_content
        messages.append(msg)
