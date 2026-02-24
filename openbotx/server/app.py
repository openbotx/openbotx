import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse

from openbotx.bus.events import InboundMessage
from openbotx.bus.queue import MessageBus
from openbotx.channels.manager import ChannelManager
from openbotx.config.loader import load_config
from openbotx.cron.service import CronService
from openbotx.cron.types import CronJob
from openbotx.providers.litellm_provider import LiteLLMProvider
from openbotx.server.auth import AuthMiddleware
from openbotx.server.websocket import WebSocketManager, websocket_endpoint
from openbotx.session.manager import SessionManager
from openbotx.tasks.manager import TaskManager
from openbotx.agent.skills import SkillsLoader
from openbotx.agent.subagent import SubagentManager
from openbotx.agent.loop import AgentLoop
from openbotx.version import __version__

logger = logging.getLogger(__name__)

WEBCLIENT_DIR = Path(__file__).parent.parent.parent / "webclient" / "dist"


def _build_cron_callback(bus: MessageBus):
    async def _on_job(job: CronJob) -> None:
        msg = InboundMessage(
            channel=job.payload.channel or "web",
            sender_id="cron",
            chat_id=job.payload.to or "direct",
            content=job.payload.message,
            metadata={"cron_job_id": job.id, "cron_job_name": job.name},
        )
        await bus.publish_inbound(msg)

    return _on_job


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = load_config()
    workspace = config.workspace_path
    workspace.mkdir(parents=True, exist_ok=True)

    if not config.auth.secret_key:
        config.auth.secret_key = uuid4().hex

    app.state.auth_secret = config.auth.secret_key

    ws_manager = WebSocketManager()
    bus = MessageBus()
    session_manager = SessionManager(workspace)
    task_manager = TaskManager(workspace, ws_manager)
    skills_loader = SkillsLoader(workspace)
    cron_service = CronService(workspace, on_job_callback=_build_cron_callback(bus))

    main_agent = config.main_agent
    provider_cfg = config.get_provider()
    provider = LiteLLMProvider(
        api_key=provider_cfg.api_key if provider_cfg else "",
        api_base=provider_cfg.api_base if provider_cfg else None,
    )

    subagent_manager = SubagentManager(
        provider=provider,
        workspace=workspace,
        bus=bus,
        ws_manager=ws_manager,
        task_manager=task_manager,
        model=main_agent.model,
        brave_api_key=config.tools.web_search.api_key,
        exec_timeout=config.tools.exec.timeout,
        restrict_to_workspace=config.tools.restrict_to_workspace,
    )

    agent_loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=workspace,
        ws_manager=ws_manager,
        task_manager=task_manager,
        session_manager=session_manager,
        skills_loader=skills_loader,
        subagent_manager=subagent_manager,
        cron_service=cron_service,
        model=main_agent.model,
        max_iterations=main_agent.params.max_iterations,
        temperature=main_agent.params.temperature,
        max_tokens=main_agent.params.max_tokens,
        memory_window=main_agent.params.memory_window,
        brave_api_key=config.tools.web_search.api_key,
        exec_timeout=config.tools.exec.timeout,
        restrict_to_workspace=config.tools.restrict_to_workspace,
        image_config=config.image,
    )

    channel_manager = ChannelManager(config.channels, bus, ws_manager=ws_manager)

    app.state.config = config
    app.state.ws_manager = ws_manager
    app.state.bus = bus
    app.state.session_manager = session_manager
    app.state.task_manager = task_manager
    app.state.skills_loader = skills_loader
    app.state.cron_service = cron_service
    app.state.provider = provider
    app.state.subagent_manager = subagent_manager
    app.state.agent_loop = agent_loop
    app.state.channel_manager = channel_manager

    agent_task = asyncio.create_task(agent_loop.run())
    cron_task = asyncio.create_task(cron_service.run())
    await channel_manager.start()

    logger.info("openbotx %s started (workspace: %s)", __version__, workspace)

    yield

    await agent_loop.stop()
    agent_task.cancel()
    try:
        await agent_task
    except asyncio.CancelledError:
        pass

    await cron_service.stop()
    cron_task.cancel()
    try:
        await cron_task
    except asyncio.CancelledError:
        pass

    await channel_manager.stop()

    logger.info("openbotx shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(title="OpenBotX", version=__version__, lifespan=lifespan)

    app.add_middleware(AuthMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from openbotx.server.routes import (
        auth,
        system,
        chat,
        tasks,
        files,
        skills,
        channels,
        providers,
        scheduler,
        config,
    )

    app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
    app.include_router(system.router, prefix="/api", tags=["system"])
    app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
    app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
    app.include_router(files.router, prefix="/api/files", tags=["files"])
    app.include_router(skills.router, prefix="/api/skills", tags=["skills"])
    app.include_router(channels.router, prefix="/api/channels", tags=["channels"])
    app.include_router(providers.router, prefix="/api/providers", tags=["providers"])
    app.include_router(scheduler.router, prefix="/api/scheduler", tags=["scheduler"])
    app.include_router(config.router, prefix="/api/config", tags=["config"])

    app.add_api_websocket_route("/ws", websocket_endpoint)

    @app.get("/")
    async def root_redirect():
        return RedirectResponse("/app/")

    if WEBCLIENT_DIR.is_dir():
        @app.get("/app/{path:path}")
        async def spa_fallback(path: str):
            file_path = WEBCLIENT_DIR / path
            if file_path.is_file():
                return FileResponse(file_path)
            return FileResponse(WEBCLIENT_DIR / "index.html")

    return app


app = create_app()
