from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from openbotx.agent.context import ContextBuilder
from openbotx.agent.memory import MemoryStore
from openbotx.agent.skills import SkillsLoader
from openbotx.agent.subagent import SubagentManager
from openbotx.bus.dispatcher import EventDispatcher
from openbotx.bus.events import InboundMessage, OutboundMessage
from openbotx.bus.queue import MessageBus
from openbotx.cron.service import CronService
from openbotx.helpers.path import PathResolver
from openbotx.helpers.text import describe_tool_use, humanize
from openbotx.providers.base import LLMProvider
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
from openbotx.tools.rss import RssReaderTool
from openbotx.tools.shell import ExecTool
from openbotx.tools.spawn import SpawnTool
from openbotx.tools.twitter import TwitterTool
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
        project_path: Path,
        workspace: Path,
        resolver: PathResolver,
        public_dir: Path,
        dispatcher: EventDispatcher | None,
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
        image_config=None,
        twitter_config=None,
        storage=None,
        public_url: str = "",
        agent_name: str = "main",
        agent_instructions: str = "",
        agent_tools: list[str] | None = None,
    ):
        self._bus = bus
        self._provider = provider
        self._project_path = project_path
        self._workspace = workspace
        self._resolver = resolver
        self._public_dir = public_dir
        self._storage = storage
        self._dispatcher = dispatcher
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
        self._image_config = image_config
        self._twitter_config = twitter_config
        self._agent_name = agent_name
        self._agent_instructions = agent_instructions
        self._agent_tools = agent_tools

        self._memory = MemoryStore(workspace)
        self._context_builder = ContextBuilder(
            workspace=workspace,
            public_dir=public_dir,
            project_path=project_path,
            memory=self._memory,
            skills_loader=skills_loader,
            public_url=public_url,
        )
        self._registry = ToolRegistry()

        self._message_tool: MessageTool | None = None
        self._spawn_tool: SpawnTool | None = None
        self._cron_tool: CronTool | None = None

        self._register_tools()

    @property
    def name(self) -> str:
        return self._agent_name

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Return tool definitions from the registry."""
        return self._registry.get_definitions()

    def _register_tools(self) -> None:
        whitelist = set(self._agent_tools) if self._agent_tools else None

        def _register(tool):
            if whitelist and tool.name not in whitelist:
                return
            self._registry.register(tool)

        _register(ReadFileTool(self._resolver))
        _register(WriteFileTool(self._resolver))
        _register(EditFileTool(self._resolver))
        _register(ListDirTool(self._resolver))
        _register(
            ExecTool(
                timeout=self._exec_timeout,
                working_dir=str(self._workspace),
                restrict_to_workspace=self._resolver.is_restricted,
            )
        )
        _register(WebSearchTool(api_key=self._brave_api_key))
        _register(WebFetchTool())

        self._message_tool = MessageTool(send_callback=self._bus.publish_outbound)
        _register(self._message_tool)

        self._spawn_tool = SpawnTool(manager=self._subagent_manager)
        _register(self._spawn_tool)

        if self._cron_service:
            self._cron_tool = CronTool(cron_service=self._cron_service)
            _register(self._cron_tool)

        _register(SaveMemoryTool(memory_store=self._memory))
        _register(BrowserTool())
        _register(HttpClientTool(self._resolver))
        _register(RssReaderTool())

        if self._image_config and self._image_config.provider.api_key and self._storage:
            _register(ImageGenerationTool(config=self._image_config, storage=self._storage))

        if self._twitter_config and self._twitter_config.consumer_key and self._storage:
            _register(TwitterTool(config=self._twitter_config, storage=self._storage))

    async def stop(self) -> None:
        browser_tool = self._registry.get("browser")
        if browser_tool and hasattr(browser_tool, "cleanup"):
            await browser_tool.cleanup()

    async def process_message(self, msg: InboundMessage, agent_name: str = "") -> None:
        effective_name = agent_name or self._agent_name
        task_id = msg.metadata.get("task_id")
        task = None

        if task_id:
            task = self._task_manager.get_task(task_id)

        if not task:
            task = await self._task_manager.create_task(
                title=msg.content[:50],
                description=msg.content,
                agent_name=effective_name,
                channel=msg.channel,
                chat_id=msg.chat_id,
            )
            task_id = task.id

        if task.agent_name != effective_name:
            task.agent_name = effective_name

        await self._task_manager.update_state(task_id, TaskState.DOING)

        if msg.channel != "web" and self._dispatcher:
            await self._dispatcher.broadcast(
                "chat:user_message",
                {
                    "chat_id": msg.chat_id,
                    "content": msg.content,
                    "media": msg.media,
                    "channel": msg.channel,
                },
            )

        session = self._session_manager.get_or_create(msg.session_key)

        content = msg.content.strip()

        if content.lower() == "/new":
            session.clear()
            self._session_manager.save(session)
            await self._task_manager.update_state(task_id, TaskState.DONE)
            if self._dispatcher:
                await self._dispatcher.broadcast("sessions:updated", {})
            await self._bus.publish_outbound(
                OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content="Conversation cleared. How can I help you?",
                    metadata={"task_id": task_id, "agent_name": effective_name},
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
                    metadata={"task_id": task_id, "agent_name": effective_name},
                )
            )
            return

        if self._message_tool:
            self._message_tool.set_context(msg.channel, msg.chat_id, msg.metadata.get("message_id"))
            self._message_tool.start_turn()

        if self._spawn_tool:
            self._spawn_tool.set_context(
                msg.channel, msg.chat_id, parent_task_id=task_id, agent_name=effective_name
            )

        if self._cron_tool:
            self._cron_tool.set_context(msg.channel, msg.chat_id)

        extra_content = ""
        media_urls = None
        if msg.media:
            extra_content, image_uris = await self._resolve_media(msg.media)
            media_urls = image_uris or None

        if extra_content:
            content = f"{content}\n\n{extra_content}"
            if self._dispatcher:
                await self._dispatcher.broadcast(
                    "chat:transcription",
                    {"chat_id": msg.chat_id, "content": extra_content},
                )

        system_prompt = self._context_builder.build_system_prompt(
            agent_name=effective_name,
            agent_instructions=self._agent_instructions,
        )
        history = session.get_history()
        messages = ContextBuilder.build_messages(system_prompt, history, content, media=media_urls)

        try:
            response_text = await self._run_agent_loop(
                messages, task_id, msg.chat_id, effective_name
            )
        except Exception as e:
            logger.error("agent loop error for task %s: %s", task_id, e, exc_info=True)
            response_text = f"I encountered an error: {e}"
            await self._task_manager.update_state(task_id, TaskState.ERROR, error=str(e))
            await self._bus.publish_outbound(
                OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=response_text,
                    metadata={"task_id": task_id, "agent_name": effective_name},
                )
            )
            return

        user_kwargs = {}
        if msg.media:
            user_kwargs["media"] = msg.media
        session.add_message("user", content, **user_kwargs)
        session.add_message("assistant", response_text, agent_name=effective_name)
        self._session_manager.save(session)

        if self._dispatcher:
            await self._dispatcher.broadcast("sessions:updated", {})

        await self._bus.publish_outbound(
            OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=response_text,
                metadata={"task_id": task_id, "agent_name": effective_name},
            )
        )

        await self._task_manager.update_state(task_id, TaskState.DONE, result=response_text[:200])

        await self._check_consolidation(session)

    async def _run_agent_loop(
        self,
        messages: list[dict[str, Any]],
        task_id: str,
        chat_id: str = "",
        agent_name: str = "",
    ) -> str:
        for iteration in range(self._max_iterations):
            response = await self._provider.chat(
                messages=messages,
                tools=self._registry.get_definitions(),
                model=self._model,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
            )

            if response.reasoning_content and self._dispatcher:
                await self._dispatcher.broadcast(
                    "chat:thinking",
                    {
                        "task_id": task_id,
                        "chat_id": chat_id,
                        "content": response.reasoning_content,
                        "agent_name": agent_name,
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

                    if self._dispatcher:
                        display_name = humanize(tc.name)
                        description = describe_tool_use(tc.name, tc.arguments)
                        await self._dispatcher.broadcast(
                            "chat:tool_use",
                            {
                                "task_id": task_id,
                                "chat_id": chat_id,
                                "tool": display_name,
                                "description": description,
                                "agent_name": agent_name,
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

    _AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".m4a", ".webm", ".aac", ".flac"}

    async def _resolve_media(self, paths: list[str]) -> tuple[str, list[str]]:
        """Resolve media paths: transcribe audio, convert images to data URIs.

        Returns (transcription_text, image_data_uris).
        """
        transcriptions: list[str] = []
        image_uris: list[str] = []

        for path in paths:
            ext = Path(path).suffix.lower()

            if ext in self._AUDIO_EXTENSIONS:
                if self._storage:
                    try:
                        data = await self._storage.read(path)
                        from openbotx.helpers.transcription import transcribe

                        text = transcribe(data)
                        if text:
                            transcriptions.append(f"[Audio transcription]: {text}")
                    except Exception as e:
                        logger.warning("audio transcription failed for %s: %s", path, e)
            elif path.startswith("data:"):
                image_uris.append(path)
            elif self._storage:
                image_uris.append(self._storage.get_data_uri(path))

        return "\n".join(transcriptions), image_uris
