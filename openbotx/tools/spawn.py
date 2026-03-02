from typing import Any, Protocol

from openbotx.tools.base import Tool
from openbotx.tools.context import RequestContext


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

    async def execute(self, task: str, label: str | None = None, **kwargs: Any) -> str:
        ctx: RequestContext | None = kwargs.get("_context")
        return await self._manager.spawn(
            task=task,
            label=label,
            origin_channel=ctx.channel if ctx else "web",
            origin_chat_id=ctx.chat_id if ctx else "direct",
            parent_task_id=ctx.task_id if ctx else None,
            agent_name=ctx.agent_name if ctx else "",
        )
