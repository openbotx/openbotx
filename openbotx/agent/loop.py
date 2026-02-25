from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from openbotx.agent.context import ContextBuilder
from openbotx.agent.memory import MemoryStore
from openbotx.agent.skills import SkillsLoader
from openbotx.agent.subagent import SubagentManager
from openbotx.bus.events import InboundMessage, OutboundMessage
from openbotx.bus.queue import MessageBus
from openbotx.cron.service import CronService
from openbotx.helpers.text import describe_tool_use, humanize
from openbotx.providers.base import LLMProvider
from openbotx.server.websocket import WebSocketManager
from openbotx.session.manager import SessionManager
from openbotx.tasks.manager import TaskManager
from openbotx.tasks.models import TaskState
from openbotx.tools.browser import BrowserTool
from openbotx.tools.cron import CronTool
from openbotx.tools.filesystem import (
    EditFileTool,
    ListDirTool,
    ReadFileTool,
    WriteFileTool,
)
from openbotx.tools.http_client import HttpClientTool
from openbotx.tools.image import ImageGenerationTool
from openbotx.tools.memory_tool import SaveMemoryTool
from openbotx.tools.message import MessageTool
from openbotx.tools.registry import ToolRegistry
from openbotx.tools.shell import ExecTool
from openbotx.tools.spawn import SpawnTool
from openbotx.tools.web import WebFetchTool, WebSearchTool

logger = logging.getLogger(__name__)


class AgentLoop:
    _HELP_TEXT = (
        "Available commands:\n  /new - Start a new conversation\n  /help - Show this help message\n"
    )

    def __init__(
        self,
        bus: MessageBus,
        provider: LLMProvider,
        workspace: Path,
        ws_manager: WebSocketManager | None,
        task_manager: TaskManager,
        session_manager: SessionManager,
        skills_loader: SkillsLoader,
        subagent_manager: SubagentManager,
        cron_service: CronService | None,
        model: str,
        max_iterations: int = 40,
        temperature: float = 0.1,
        max_tokens: int = 8192,
        memory_window: int = 100,
        brave_api_key: str = "",
        exec_timeout: int = 60,
        restrict_to_workspace: bool = True,
        image_config=None,
        storage=None,
    ):
        self._bus = bus
        self._provider = provider
        self._workspace = workspace
        self._storage = storage
        self._ws_manager = ws_manager
        self._task_manager = task_manager
        self._session_manager = session_manager
        self._skills_loader = skills_loader
        self._subagent_manager = subagent_manager
        self._cron_service = cron_service
        self._model = model
        self._max_iterations = max_iterations
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._memory_window = memory_window
        self._brave_api_key = brave_api_key
        self._exec_timeout = exec_timeout
        self._restrict_to_workspace = restrict_to_workspace
        self._image_config = image_config

        self._memory = MemoryStore(workspace)
        self._context_builder = ContextBuilder(workspace, self._memory, skills_loader)
        self._registry = ToolRegistry()
        self._stop_event = asyncio.Event()

        self._message_tool: MessageTool | None = None
        self._spawn_tool: SpawnTool | None = None
        self._cron_tool: CronTool | None = None

        self._register_tools()

    def _register_tools(self) -> None:
        allowed_dir = self._workspace if self._restrict_to_workspace else None

        self._registry.register(ReadFileTool(workspace=self._workspace, allowed_dir=allowed_dir))
        self._registry.register(WriteFileTool(workspace=self._workspace, allowed_dir=allowed_dir))
        self._registry.register(EditFileTool(workspace=self._workspace, allowed_dir=allowed_dir))
        self._registry.register(ListDirTool(workspace=self._workspace, allowed_dir=allowed_dir))
        self._registry.register(
            ExecTool(
                timeout=self._exec_timeout,
                working_dir=str(self._workspace),
                restrict_to_workspace=self._restrict_to_workspace,
            )
        )
        self._registry.register(WebSearchTool(api_key=self._brave_api_key))
        self._registry.register(WebFetchTool())

        self._message_tool = MessageTool(send_callback=self._bus.publish_outbound)
        self._registry.register(self._message_tool)

        self._spawn_tool = SpawnTool(manager=self._subagent_manager)
        self._registry.register(self._spawn_tool)

        if self._cron_service:
            self._cron_tool = CronTool(cron_service=self._cron_service)
            self._registry.register(self._cron_tool)

        self._registry.register(SaveMemoryTool(memory_store=self._memory))
        self._registry.register(BrowserTool())
        self._registry.register(HttpClientTool())

        if self._image_config and self._image_config.provider.api_key and self._storage:
            self._registry.register(
                ImageGenerationTool(config=self._image_config, storage=self._storage)
            )

    async def run(self) -> None:
        logger.info("agent loop started (model=%s)", self._model)
        while not self._stop_event.is_set():
            try:
                msg = await asyncio.wait_for(self._bus.consume_inbound(), timeout=1.0)
                await self._process_message(msg)
            except TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("error processing message: %s", e, exc_info=True)

    async def stop(self) -> None:
        self._stop_event.set()

        browser_tool = self._registry.get("browser")
        if browser_tool and hasattr(browser_tool, "cleanup"):
            await browser_tool.cleanup()

    async def _process_message(self, msg: InboundMessage) -> None:
        task_id = msg.metadata.get("task_id")
        task = None

        if task_id:
            task = self._task_manager.get_task(task_id)

        if not task:
            task = await self._task_manager.create_task(
                title=msg.content[:50],
                description=msg.content,
                channel=msg.channel,
                chat_id=msg.chat_id,
            )
            task_id = task.id

        await self._task_manager.update_state(task_id, TaskState.DOING)

        session = self._session_manager.get_or_create(msg.session_key)

        content = msg.content.strip()

        if content.lower() == "/new":
            session.clear()
            self._session_manager.save(session)
            await self._task_manager.update_state(task_id, TaskState.DONE)
            if self._ws_manager:
                await self._ws_manager.broadcast("sessions:updated", {})
            await self._bus.publish_outbound(
                OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content="Conversation cleared. How can I help you?",
                    metadata={"task_id": task_id},
                )
            )
            return

        if content.lower() == "/help":
            await self._task_manager.update_state(task_id, TaskState.DONE)
            await self._bus.publish_outbound(
                OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=self._HELP_TEXT,
                    metadata={"task_id": task_id},
                )
            )
            return

        if self._message_tool:
            self._message_tool.set_context(msg.channel, msg.chat_id, msg.metadata.get("message_id"))
            self._message_tool.start_turn()

        if self._spawn_tool:
            self._spawn_tool.set_context(msg.channel, msg.chat_id, parent_task_id=task_id)

        if self._cron_tool:
            self._cron_tool.set_context(msg.channel, msg.chat_id)

        media_urls = await self._resolve_media(msg.media) if msg.media else None

        system_prompt = self._context_builder.build_system_prompt()
        history = session.get_history()
        messages = ContextBuilder.build_messages(system_prompt, history, content, media=media_urls)

        try:
            response_text = await self._run_agent_loop(messages, task_id, msg.chat_id)
        except Exception as e:
            logger.error("agent loop error for task %s: %s", task_id, e, exc_info=True)
            response_text = f"I encountered an error: {e}"
            await self._task_manager.update_state(task_id, TaskState.ERROR, error=str(e))
            await self._bus.publish_outbound(
                OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=response_text,
                    metadata={"task_id": task_id},
                )
            )
            return

        session.add_message("user", content)
        session.add_message("assistant", response_text)
        self._session_manager.save(session)

        if self._ws_manager:
            await self._ws_manager.broadcast("sessions:updated", {})

        await self._bus.publish_outbound(
            OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=response_text,
                metadata={"task_id": task_id},
            )
        )

        await self._task_manager.update_state(task_id, TaskState.DONE, result=response_text[:200])

        await self._check_consolidation(session)

    async def _run_agent_loop(
        self, messages: list[dict[str, Any]], task_id: str, chat_id: str = ""
    ) -> str:
        for iteration in range(self._max_iterations):
            response = await self._provider.chat(
                messages=messages,
                tools=self._registry.get_definitions(),
                model=self._model,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
            )

            if response.reasoning_content and self._ws_manager:
                await self._ws_manager.broadcast(
                    "chat:thinking",
                    {
                        "task_id": task_id,
                        "chat_id": chat_id,
                        "content": response.reasoning_content,
                    },
                )

            if response.has_tool_calls:
                tool_calls_data = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in response.tool_calls
                ]

                ContextBuilder.add_assistant_message(
                    messages,
                    response.content,
                    tool_calls=tool_calls_data,
                    reasoning_content=response.reasoning_content,
                )

                for tc in response.tool_calls:
                    result = await self._registry.execute(tc.name, tc.arguments)

                    if self._ws_manager:
                        display_name = humanize(tc.name)
                        description = describe_tool_use(tc.name, tc.arguments)
                        await self._ws_manager.broadcast(
                            "chat:tool_use",
                            {
                                "task_id": task_id,
                                "chat_id": chat_id,
                                "tool": display_name,
                                "description": description,
                            },
                        )

                    ContextBuilder.add_tool_result(messages, tc.id, tc.name, result)
            else:
                return response.content or ""

        logger.warning("agent loop hit max iterations (%d)", self._max_iterations)
        return "I've reached my processing limit. Please try again or simplify your request."

    async def _check_consolidation(self, session: Any) -> None:
        total = len(session.messages)
        unconsolidated = total - session.last_consolidated

        if unconsolidated < self._memory_window:
            return

        logger.info(
            "triggering memory consolidation for session %s (%d unconsolidated)",
            session.key,
            unconsolidated,
        )

        consolidation_messages = self._memory.get_consolidation_messages(
            session, self._memory_window
        )
        if not consolidation_messages:
            return

        consolidation_registry = ToolRegistry()
        consolidation_registry.register(SaveMemoryTool(memory_store=self._memory))

        try:
            for _ in range(5):
                response = await self._provider.chat(
                    messages=consolidation_messages,
                    tools=consolidation_registry.get_definitions(),
                    model=self._model,
                    max_tokens=4096,
                    temperature=0.1,
                )

                if response.has_tool_calls:
                    tool_calls_data = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments),
                            },
                        }
                        for tc in response.tool_calls
                    ]

                    consolidation_messages.append(
                        {
                            "role": "assistant",
                            "content": response.content or "",
                            "tool_calls": tool_calls_data,
                        }
                    )

                    for tc in response.tool_calls:
                        result = await consolidation_registry.execute(tc.name, tc.arguments)
                        consolidation_messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "name": tc.name,
                                "content": result,
                            }
                        )
                else:
                    break

            self._memory.mark_consolidated(session, total)
            self._session_manager.save(session)
            logger.info("memory consolidation completed for session %s", session.key)

        except Exception as e:
            logger.error("memory consolidation failed: %s", e, exc_info=True)

    async def _resolve_media(self, paths: list[str]) -> list[str]:
        resolved = []
        for path in paths:
            if path.startswith("data:"):
                resolved.append(path)
                continue
            if self._storage:
                resolved.append(self._storage.get_data_uri(path))
            else:
                resolved.append(path)
        return resolved
