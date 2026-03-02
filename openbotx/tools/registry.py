import logging
from dataclasses import dataclass
from typing import Any

from openbotx.agent.memory import MemoryStore
from openbotx.bus.queue import MessageBus
from openbotx.config.project import ProjectContext
from openbotx.config.schema import AgentConfig
from openbotx.cron.service import CronService
from openbotx.tools.base import Tool
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
from openbotx.tools.memory_tool import MemoryReadTool, MemorySaveTool, MemorySearchTool
from openbotx.tools.message import MessageTool
from openbotx.tools.rss import RssReaderTool
from openbotx.tools.shell import ExecTool
from openbotx.tools.spawn import SpawnManager, SpawnTool
from openbotx.tools.web import WebFetchTool, WebSearchTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry for agent tools."""

    _HINT = "\n\n[Analyze the error above and try a different approach.]"
    _MAX_RESULT_CHARS = 100_000

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def has(self, name: str) -> bool:
        return name in self._tools

    def get_definitions(self) -> list[dict[str, Any]]:
        return [tool.to_schema() for tool in self._tools.values()]

    async def execute(self, name: str, params: dict[str, Any]) -> str:
        tool = self._tools.get(name)
        if not tool:
            return f"Error: Tool '{name}' not found. Available: {', '.join(self.tool_names)}"

        try:
            errors = tool.validate_params(params)
            if errors:
                return (
                    f"Error: Invalid parameters for tool '{name}': "
                    + "; ".join(errors)
                    + self._HINT
                )
            result = await tool.execute(**params)
            if isinstance(result, str) and result.startswith("Error"):
                return result + self._HINT
            # truncate oversized results to prevent context overflow
            if isinstance(result, str) and len(result) > self._MAX_RESULT_CHARS:
                result = (
                    result[: self._MAX_RESULT_CHARS]
                    + f"\n\n[Output truncated: {len(result)} total chars, showing first {self._MAX_RESULT_CHARS}]"
                )
            return result
        except Exception as e:
            logger.error("tool %s failed: %s", name, e, exc_info=True)
            return f"Error executing {name}: {e}" + self._HINT

    @property
    def tool_names(self) -> list[str]:
        return list(self._tools.keys())

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools


@dataclass
class RegistryResult:
    registry: ToolRegistry
    message_tool: MessageTool | None = None
    spawn_tool: SpawnTool | None = None
    cron_tool: CronTool | None = None


def build_registry(
    agent_cfg: AgentConfig,
    project_ctx: ProjectContext,
    bus: MessageBus | None = None,
    subagent_manager: SpawnManager | None = None,
    cron_service: CronService | None = None,
    memory_store: MemoryStore | None = None,
    denied_tools: set[str] | None = None,
) -> RegistryResult:
    """Build a ToolRegistry with all tools configured from context objects."""
    whitelist = set(agent_cfg.tools) if agent_cfg.tools else None
    denylist = set(agent_cfg.denied_tools) | (denied_tools or set())
    registry = ToolRegistry()

    resolver = project_ctx.create_resolver(agent_cfg)
    workspace = agent_cfg.resolve_workspace(project_ctx.project_path)

    def _register(tool: Tool) -> None:
        if tool.name in denylist:
            return
        if whitelist and tool.name not in whitelist:
            return
        registry.register(tool)

    _register(ReadFileTool(resolver))
    _register(WriteFileTool(resolver))
    _register(EditFileTool(resolver))
    _register(ListDirTool(resolver))
    _register(
        ExecTool(
            timeout=project_ctx.tools.exec.timeout,
            working_dir=str(workspace),
            restrict_to_workspace=resolver.is_restricted,
        )
    )

    # web search — resolve api_key from credentials
    ws_auth = project_ctx.credentials.get(project_ctx.tools.web_search.credential)
    _register(
        WebSearchTool(
            api_key=ws_auth.key if ws_auth else "",
            max_results=project_ctx.tools.web_search.max_results,
        )
    )
    _register(WebFetchTool())

    # http client — all oauth1/basic/simple/bearer/header credentials are available as profiles
    http_profiles = {
        name: cred
        for name, cred in project_ctx.credentials.items()
        if cred.type in ("oauth1", "basic", "simple", "bearer", "header")
    }
    _register(HttpClientTool(resolver, auth_profiles=http_profiles))
    _register(RssReaderTool())
    _register(BrowserTool())

    message_tool = None
    if bus is not None:
        message_tool = MessageTool(send_callback=bus.publish_outbound)
        _register(message_tool)

    spawn_tool = None
    if subagent_manager is not None:
        spawn_tool = SpawnTool(manager=subagent_manager)
        _register(spawn_tool)

    cron_tool = None
    if cron_service is not None:
        cron_tool = CronTool(cron_service=cron_service)
        _register(cron_tool)

    if memory_store is not None:
        _register(MemorySaveTool(memory_store=memory_store))
        _register(MemoryReadTool(memory_store=memory_store))
        _register(MemorySearchTool(memory_store=memory_store))

    # image — resolve provider from model prefix (same pattern as agents)
    img_cfg = project_ctx.image
    img_prefix = img_cfg.model.split("/", 1)[0] if "/" in img_cfg.model else ""
    prov = project_ctx.providers.get(img_prefix) if img_prefix else None
    if prov:
        img_cred = project_ctx.credentials.get(prov.credential)
        if img_cred and img_cred.key and project_ctx.storage:
            _register(
                ImageGenerationTool(
                    config=img_cfg,
                    provider=prov,
                    credential=img_cred,
                    storage=project_ctx.storage,
                )
            )

    return RegistryResult(
        registry=registry,
        message_tool=message_tool,
        spawn_tool=spawn_tool,
        cron_tool=cron_tool,
    )
