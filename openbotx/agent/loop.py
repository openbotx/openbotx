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
from openbotx.config.project import ProjectContext
from openbotx.config.schema import AgentConfig
from openbotx.cron.service import CronService
from openbotx.helpers.text import describe_tool_use, humanize
from openbotx.providers.base import LLMProvider, LLMResponse, ToolCallRequest
from openbotx.session.manager import SessionManager
from openbotx.tasks.manager import TaskManager
from openbotx.tasks.models import TaskState
from openbotx.tools.memory_tool import MemorySaveTool
from openbotx.tools.registry import ToolRegistry, build_registry

logger = logging.getLogger(__name__)


class AgentLoop:
    _HELP_TEXT = (
        "Available commands:\n  /new - Start a new conversation\n  /help - Show this help message\n"
    )

    def __init__(
        self,
        agent_cfg: AgentConfig,
        project_ctx: ProjectContext,
        bus: MessageBus,
        provider: LLMProvider,
        dispatcher: EventDispatcher,
        task_manager: TaskManager,
        session_manager: SessionManager,
        skills_loader: SkillsLoader,
        subagent_manager: SubagentManager,
        cron_service: CronService | None,
    ):
        self._agent_cfg = agent_cfg
        self._project_ctx = project_ctx
        self._bus = bus
        self._provider = provider
        self._dispatcher = dispatcher
        self._task_manager = task_manager
        self._session_manager = session_manager

        workspace = agent_cfg.resolve_workspace(project_ctx.project_path)
        self._workspace = workspace

        self._memory = MemoryStore(workspace)
        self._context_builder = ContextBuilder(
            project_ctx=project_ctx,
            workspace=workspace,
            memory=self._memory,
            skills_loader=skills_loader,
        )

        result = build_registry(
            agent_cfg=agent_cfg,
            project_ctx=project_ctx,
            bus=bus,
            subagent_manager=subagent_manager,
            cron_service=cron_service,
            memory_store=self._memory,
        )
        self._registry = result.registry
        self._message_tool = result.message_tool
        self._spawn_tool = result.spawn_tool
        self._cron_tool = result.cron_tool

    @property
    def name(self) -> str:
        return self._agent_cfg.name

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Return tool definitions from the registry."""
        return self._registry.get_definitions()

    async def stop(self) -> None:
        browser_tool = self._registry.get("browser")
        if browser_tool and hasattr(browser_tool, "cleanup"):
            await browser_tool.cleanup()

    async def process_message(self, msg: InboundMessage, agent_name: str = "") -> None:
        effective_name = agent_name or self._agent_cfg.name
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

        task.live_state = {"tool_uses": []}
        await self._task_manager.update_state(task_id, TaskState.DOING)

        if msg.channel != "web":
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
        session.live_state = {"tool_uses": [], "agent_name": effective_name}

        content = msg.content.strip()

        if content.lower() == "/new":
            session.clear()
            self._session_manager.save(session)
            await self._task_manager.update_state(task_id, TaskState.DONE)
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
            await self._dispatcher.broadcast(
                "chat:transcription",
                {"chat_id": msg.chat_id, "content": extra_content},
            )

        # Save user message if not already persisted at the HTTP layer.
        if not msg.metadata.get("message_saved"):
            user_kwargs = {}
            if msg.media:
                user_kwargs["media"] = msg.media
            session.add_message("user", content, **user_kwargs)
            self._session_manager.save(session)
            await self._dispatcher.broadcast("sessions:updated", {})

        system_prompt = self._context_builder.build_system_prompt(
            agent_name=effective_name,
            agent_instructions=self._agent_cfg.instructions,
            channel=msg.channel,
            tool_names=self._registry.tool_names,
        )

        # Build LLM context. The user message is already in session history,
        # so exclude it — build_messages appends the current turn separately.
        history = session.get_history()
        if history and history[-1]["role"] == "user":
            history = history[:-1]
        messages = ContextBuilder.build_messages(system_prompt, history, content, media=media_urls)

        try:
            response_text = await self._run_agent_loop(
                messages, task_id, msg.chat_id, effective_name, session
            )
        except Exception as e:
            session.live_state = {}
            task.live_state = {}
            logger.error("agent loop error for task %s: %s", task_id, e, exc_info=True)
            response_text = f"I encountered an error: {e}"
            session.add_message("assistant", response_text, agent_name=effective_name)
            self._session_manager.save(session)
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

        session.live_state = {}
        task.live_state = {}
        session.add_message("assistant", response_text, agent_name=effective_name)
        self._session_manager.save(session)

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
        session: Any = None,
    ) -> str:
        from openbotx.agent.compaction import compact_messages
        from openbotx.agent.context_window import needs_compaction
        from openbotx.agent.usage import UsageTracker
        from openbotx.providers.errors import ContextOverflowError

        max_iterations = self._agent_cfg.agent_params.max_iterations
        _recent_tool_sigs: list[str] = []
        usage_tracker = UsageTracker()

        for iteration in range(max_iterations):
            self._task_manager.increment_iteration_count(task_id)

            # compact context if approaching model limit
            if needs_compaction(messages, self._agent_cfg.model, self._agent_cfg.model_params):
                logger.info(
                    "context window near limit, compacting (task %s, iteration %d)",
                    task_id,
                    iteration,
                )
                messages = await compact_messages(messages, self._provider, self._agent_cfg.model)

            try:
                response = await self._consume_stream(
                    messages,
                    task_id,
                    chat_id,
                    agent_name,
                    usage_tracker,
                )
            except ContextOverflowError:
                logger.warning("context overflow, forcing compaction (task %s)", task_id)
                messages = await compact_messages(messages, self._provider, self._agent_cfg.model)
                response = await self._consume_stream(
                    messages,
                    task_id,
                    chat_id,
                    agent_name,
                    usage_tracker,
                )

            if response.has_tool_calls:
                # detect tool call loop (same calls repeated)
                sig = "|".join(
                    f"{tc.name}:{json.dumps(tc.arguments, sort_keys=True)}"
                    for tc in response.tool_calls
                )
                if sig in _recent_tool_sigs:
                    logger.warning(
                        "tool call loop detected at iteration %d (task %s)", iteration, task_id
                    )
                    self._save_usage(task_id, usage_tracker)
                    return (
                        response.content
                        or "I seem to be repeating the same actions. Let me stop here."
                    )
                _recent_tool_sigs.append(sig)
                if len(_recent_tool_sigs) > 3:
                    _recent_tool_sigs.pop(0)

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
                    self._task_manager.increment_tool_count(task_id)

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

                    tool_entry = {"tool": display_name, "description": description}
                    if session is not None:
                        session.live_state.setdefault("tool_uses", []).append(tool_entry)
                    task = self._task_manager.get_task(task_id)
                    if task is not None:
                        task.live_state.setdefault("tool_uses", []).append(tool_entry)

                    ContextBuilder.add_tool_result(messages, tc.id, tc.name, result)
            else:
                self._save_usage(task_id, usage_tracker)
                return response.content or ""

        self._save_usage(task_id, usage_tracker)
        logger.warning("agent loop hit max iterations (%d)", max_iterations)
        return "I've reached my processing limit. Please try again or simplify your request."

    async def _consume_stream(
        self,
        messages: list[dict[str, Any]],
        task_id: str,
        chat_id: str,
        agent_name: str,
        usage_tracker: Any,
    ) -> LLMResponse:
        """Consume a streaming response, broadcasting tokens in real time."""

        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        tool_calls: list[ToolCallRequest] = []
        usage: dict[str, int] = {}

        async for chunk in self._provider.chat_stream(
            messages=messages,
            tools=self._registry.get_definitions(),
            model=self._agent_cfg.model,
            model_params=self._agent_cfg.model_params,
        ):
            if chunk.type == "content" and chunk.content:
                content_parts.append(chunk.content)
                await self._dispatcher.broadcast(
                    "chat:stream",
                    {
                        "task_id": task_id,
                        "chat_id": chat_id,
                        "content": chunk.content,
                        "agent_name": agent_name,
                    },
                )

            elif chunk.type == "reasoning" and chunk.content:
                reasoning_parts.append(chunk.content)

            elif chunk.type == "tool_call":
                args = chunk.tool_call_arguments
                if isinstance(args, str):
                    import json_repair

                    args = json_repair.loads(args) if args else {}
                tool_calls.append(
                    ToolCallRequest(
                        id=chunk.tool_call_id,
                        name=chunk.tool_call_name,
                        arguments=args,
                    )
                )

            elif chunk.type == "usage" and chunk.usage:
                usage = chunk.usage
                usage_tracker.record(usage)

        # broadcast thinking if we accumulated reasoning
        reasoning_content = "".join(reasoning_parts) or None
        if reasoning_content:
            await self._dispatcher.broadcast(
                "chat:thinking",
                {
                    "task_id": task_id,
                    "chat_id": chat_id,
                    "content": reasoning_content,
                    "agent_name": agent_name,
                },
            )

        # signal end of stream to frontend
        if content_parts and not tool_calls:
            await self._dispatcher.broadcast(
                "chat:stream_end",
                {"task_id": task_id, "chat_id": chat_id, "agent_name": agent_name},
            )

        return LLMResponse(
            content="".join(content_parts) or None,
            tool_calls=tool_calls,
            finish_reason="tool_calls" if tool_calls else "stop",
            usage=usage,
            reasoning_content=reasoning_content,
        )

    def _save_usage(self, task_id: str, tracker: Any) -> None:
        """Persist token usage on the task."""
        task = self._task_manager.get_task(task_id)
        if task and tracker.total_tokens > 0:
            task.token_usage = tracker.to_dict()

    async def _check_consolidation(self, session: Any) -> None:
        total = len(session.messages)
        unconsolidated = total - session.last_consolidated
        memory_window = self._agent_cfg.agent_params.memory_window

        if unconsolidated < memory_window:
            return

        logger.info(
            "triggering memory consolidation for session %s (%d unconsolidated)",
            session.key,
            unconsolidated,
        )

        consolidation_messages = self._memory.get_consolidation_messages(session, memory_window)
        if not consolidation_messages:
            return

        consolidation_registry = ToolRegistry()
        consolidation_registry.register(MemorySaveTool(memory_store=self._memory))

        try:
            memory_save_called = False
            for _ in range(5):
                response = await self._provider.chat(
                    messages=consolidation_messages,
                    tools=consolidation_registry.get_definitions(),
                    model=self._agent_cfg.model,
                    model_params={"max_tokens": 4096, "temperature": 0.1},
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
                        if tc.name == "memory_save":
                            memory_save_called = True
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

            if memory_save_called:
                self._memory.mark_consolidated(session, total)
                self._session_manager.save(session)
                logger.info("memory consolidation completed for session %s", session.key)
            else:
                logger.info("memory consolidation skipped (no save) for session %s", session.key)

        except Exception as e:
            logger.error("memory consolidation failed: %s", e, exc_info=True)

    _AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".m4a", ".webm", ".aac", ".flac"}

    async def _resolve_media(self, paths: list[str]) -> tuple[str, list[str]]:
        """Resolve media paths: transcribe audio, convert images to data URIs."""
        transcriptions: list[str] = []
        image_uris: list[str] = []
        storage = self._project_ctx.storage

        for path in paths:
            ext = Path(path).suffix.lower()

            if ext in self._AUDIO_EXTENSIONS:
                if storage:
                    try:
                        data = await storage.read(path)
                        from openbotx.helpers.transcription import transcribe

                        text = transcribe(data)
                        if text:
                            transcriptions.append(f"[Audio transcription]: {text}")
                    except Exception as e:
                        logger.warning("audio transcription failed for %s: %s", path, e)
            elif path.startswith("data:"):
                image_uris.append(path)
            elif storage:
                image_uris.append(storage.get_data_uri(path))

        return "\n".join(transcriptions), image_uris
