from typing import Any, Protocol

from openbotx.tools.base import Tool


class SpawnManager(Protocol):
    async def spawn(
        self,
        task: str,
        label: str | None = None,
        origin_channel: str = "web",
        origin_chat_id: str = "direct",
        parent_task_id: str | None = None,
        agent_name: str = "",
    ) -> str: ...


class SpawnTool(Tool):
    """Spawn a subagent for background task execution."""

    name = "spawn"
    description = (
        "Spawn a subagent to handle a task in the background. "
        "The subagent will complete the task and report back when done."
    )
    parameters = {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "The task for the subagent to complete",
            },
            "label": {
                "type": "string",
                "description": "Optional short label for the task",
            },
        },
        "required": ["task"],
    }

    def __init__(self, manager: SpawnManager):
        self._manager = manager
        self._origin_channel = "web"
        self._origin_chat_id = "direct"
        self._parent_task_id: str | None = None
        self._agent_name = ""

    def set_context(
        self,
        channel: str,
        chat_id: str,
        parent_task_id: str | None = None,
        agent_name: str = "",
    ) -> None:
        self._origin_channel = channel
        self._origin_chat_id = chat_id
        self._parent_task_id = parent_task_id
        self._agent_name = agent_name

    async def execute(self, task: str, label: str | None = None, **kwargs: Any) -> str:
        return await self._manager.spawn(
            task=task,
            label=label,
            origin_channel=self._origin_channel,
            origin_chat_id=self._origin_chat_id,
            parent_task_id=self._parent_task_id,
            agent_name=self._agent_name,
        )
