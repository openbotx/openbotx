from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from openbotx.bus.events import InboundMessage
from openbotx.bus.queue import MessageBus
from openbotx.helpers.path import PathResolver
from openbotx.providers.base import LLMProvider
from openbotx.tasks.manager import TaskManager
from openbotx.tools.browser import BrowserTool
from openbotx.tools.filesystem import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
from openbotx.tools.http_client import HttpClientTool
from openbotx.tools.registry import ToolRegistry
from openbotx.tools.rss import RssReaderTool
from openbotx.tools.shell import ExecTool
from openbotx.tools.web import WebFetchTool, WebSearchTool

logger = logging.getLogger(__name__)

MAX_SUBAGENT_ITERATIONS = 15


class SubagentManager:
    def __init__(
        self,
        provider: LLMProvider,
        workspace: Path,
        resolver: PathResolver,
        public_dir: Path,
        bus: MessageBus,
        task_manager: TaskManager,
        model: str,
        brave_api_key: str = "",
        web_search_max_results: int = 5,
        exec_timeout: int = 60,
        image_config=None,
        auth_profiles=None,
        storage=None,
    ):
        self._provider = provider
        self._workspace = workspace
        self._resolver = resolver
        self._public_dir = public_dir
        self._bus = bus
        self._task_manager = task_manager
        self._model = model
        self._brave_api_key = brave_api_key
        self._web_search_max_results = web_search_max_results
        self._exec_timeout = exec_timeout
        self._image_config = image_config
        self._auth_profiles = auth_profiles or {}
        self._storage = storage
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

        registry, browser_tool = self._build_registry()

        system_prompt = (
            "You are a subagent of OpenBotX. Complete the following task and "
            "report results. Be concise and efficient.\n"
            f"Workspace: {self._workspace} (internal files)\n"
            f"Public: {self._public_dir} (web-accessible files)\n"
            "Always use absolute paths."
        )

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task_text},
        ]

        try:
            final_content = ""
            for _ in range(MAX_SUBAGENT_ITERATIONS):
                response = await self._provider.chat(
                    messages=messages,
                    tools=registry.get_definitions(),
                    model=self._model,
                    max_tokens=4096,
                    temperature=0.1,
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
                        result = await registry.execute(tc.name, tc.arguments)
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "name": tc.name,
                                "content": result[:500] if len(result) > 500 else result,
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
            if browser_tool:
                await browser_tool.close_tab()

    def _build_registry(self) -> tuple[ToolRegistry, BrowserTool | None]:
        registry = ToolRegistry()

        registry.register(ReadFileTool(self._resolver))
        registry.register(WriteFileTool(self._resolver))
        registry.register(EditFileTool(self._resolver))
        registry.register(ListDirTool(self._resolver))
        registry.register(
            ExecTool(
                timeout=self._exec_timeout,
                working_dir=str(self._workspace),
                restrict_to_workspace=self._resolver.is_restricted,
            )
        )
        registry.register(
            WebSearchTool(api_key=self._brave_api_key, max_results=self._web_search_max_results)
        )
        registry.register(WebFetchTool())
        registry.register(HttpClientTool(self._resolver, auth_profiles=self._auth_profiles))
        registry.register(RssReaderTool())

        browser_tool = BrowserTool()
        registry.register(browser_tool)

        if self._image_config and self._image_config.provider.api_key and self._storage:
            from openbotx.tools.image import ImageGenerationTool

            registry.register(ImageGenerationTool(config=self._image_config, storage=self._storage))

        return registry, browser_tool
