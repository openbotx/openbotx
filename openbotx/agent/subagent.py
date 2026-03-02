import asyncio
import json
import logging
from typing import Any

from openbotx.bus.events import InboundMessage
from openbotx.bus.queue import MessageBus
from openbotx.config.project import ProjectContext
from openbotx.config.schema import AgentConfig
from openbotx.providers.base import LLMProvider
from openbotx.tasks.manager import TaskManager
from openbotx.tools.registry import build_registry

logger = logging.getLogger(__name__)

MAX_SUBAGENT_ITERATIONS = 15

# tools that subagents must not access
_SUBAGENT_DENIED = {
    "spawn",
    "message",
    "memory_save",
    "memory_read",
    "memory_search",
    "cron",
    "exec",
    "browser",
}


class SubagentManager:
    def __init__(
        self,
        provider: LLMProvider,
        agent_cfg: AgentConfig,
        project_ctx: ProjectContext,
        bus: MessageBus,
        task_manager: TaskManager,
    ):
        self._provider = provider
        self._agent_cfg = agent_cfg
        self._project_ctx = project_ctx
        self._bus = bus
        self._task_manager = task_manager
        self._background_tasks: set[asyncio.Task] = set()

    async def spawn(
        self,
        task: str,
        label: str | None = None,
        origin_channel: str = "web",
        origin_chat_id: str = "direct",
        parent_task_id: str | None = None,
        agent_name: str = "",
    ) -> str:
        from openbotx.tasks.models import TaskState

        title = label or task[:50]
        task_obj = await self._task_manager.create_task(
            title=title,
            description=task,
            agent_type="subagent",
            agent_name=agent_name,
            channel=origin_channel,
            chat_id=origin_chat_id,
            parent_task_id=parent_task_id,
        )
        await self._task_manager.update_state(task_obj.id, TaskState.DOING)

        bg_task = asyncio.create_task(
            self._run_subagent(task_obj.id, task, origin_channel, origin_chat_id)
        )
        self._background_tasks.add(bg_task)
        bg_task.add_done_callback(self._background_tasks.discard)

        return f"Subagent spawned (task: {task_obj.id}): {title}"

    async def _run_subagent(
        self,
        task_id: str,
        task_text: str,
        origin_channel: str,
        origin_chat_id: str,
    ) -> None:
        from openbotx.tasks.models import TaskState

        result = build_registry(
            agent_cfg=self._agent_cfg,
            project_ctx=self._project_ctx,
            denied_tools=_SUBAGENT_DENIED,
        )
        registry = result.registry

        workspace = self._agent_cfg.resolve_workspace(self._project_ctx.project_path)

        system_prompt = (
            "You are a subagent of OpenBotX. Complete the following task and "
            "report results. Be concise and efficient.\n"
            f"Workspace: {workspace} (internal files)\n"
            f"Public: {self._project_ctx.public_dir} (web-accessible files)\n"
            "Always use absolute paths."
        )

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task_text},
        ]

        browser_tool = registry.get("browser")

        try:
            from openbotx.agent.compaction import compact_messages
            from openbotx.agent.context_window import needs_compaction
            from openbotx.providers.errors import ContextOverflowError

            final_content = ""
            for _ in range(MAX_SUBAGENT_ITERATIONS):
                self._task_manager.increment_iteration_count(task_id)

                # compact context if approaching model limit
                if needs_compaction(messages, self._agent_cfg.model, self._agent_cfg.model_params):
                    messages = await compact_messages(
                        messages, self._provider, self._agent_cfg.model
                    )

                try:
                    response = await self._provider.chat(
                        messages=messages,
                        tools=registry.get_definitions(),
                        model=self._agent_cfg.model,
                        model_params={"max_tokens": 4096, "temperature": 0.1},
                    )
                except ContextOverflowError:
                    messages = await compact_messages(
                        messages, self._provider, self._agent_cfg.model
                    )
                    response = await self._provider.chat(
                        messages=messages,
                        tools=registry.get_definitions(),
                        model=self._agent_cfg.model,
                        model_params={"max_tokens": 4096, "temperature": 0.1},
                    )

                if response.has_tool_calls:
                    assistant_msg: dict[str, Any] = {
                        "role": "assistant",
                        "content": response.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.name,
                                    "arguments": json.dumps(tc.arguments),
                                },
                            }
                            for tc in response.tool_calls
                        ],
                    }
                    messages.append(assistant_msg)

                    for tc in response.tool_calls:
                        tool_result = await registry.execute(tc.name, tc.arguments)
                        self._task_manager.increment_tool_count(task_id)
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "name": tc.name,
                                "content": tool_result,
                            }
                        )
                else:
                    final_content = response.content or ""
                    break

            await self._task_manager.update_state(
                task_id, TaskState.DONE, result=final_content[:500]
            )

            announcement = InboundMessage(
                channel=origin_channel,
                sender_id="system",
                chat_id=origin_chat_id,
                content=f"[Subagent {task_id} completed]: {final_content[:300]}",
                metadata={"system_message": True, "subagent_task_id": task_id},
            )
            await self._bus.publish_inbound(announcement)

        except Exception as e:
            logger.error("subagent %s failed: %s", task_id, e)
            await self._task_manager.update_state(task_id, TaskState.ERROR, error=str(e))

        finally:
            if browser_tool and hasattr(browser_tool, "close_tab"):
                await browser_tool.close_tab()
