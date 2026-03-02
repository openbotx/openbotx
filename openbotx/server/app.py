import asyncio
import logging
import logging.handlers
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from openbotx.agent.classifier import AgentClassifier
from openbotx.agent.loop import AgentLoop
from openbotx.agent.orchestrator import Orchestrator
from openbotx.agent.skills import SkillsLoader
from openbotx.agent.subagent import SubagentManager
from openbotx.bus.dispatcher import EventDispatcher
from openbotx.bus.events import InboundMessage
from openbotx.bus.queue import MessageBus
from openbotx.channels.manager import ChannelManager
from openbotx.config.loader import load_config, save_config
from openbotx.config.project import ProjectContext
from openbotx.config.schema import Config
from openbotx.cron.service import CronService
from openbotx.cron.types import CronJob
from openbotx.heartbeat.service import HeartbeatService
from openbotx.providers.litellm_provider import LiteLLMProvider
from openbotx.server.auth import AuthMiddleware
from openbotx.server.websocket import WebSocketManager, websocket_endpoint
from openbotx.session.manager import SessionManager
from openbotx.tasks.manager import TaskManager
from openbotx.version import __version__

logger = logging.getLogger(__name__)

WEB_CLIENT_DIR = Path(__file__).resolve().parent.parent / "web_client"


class ServerFactory:
    """Builds all server dependencies from config."""

    def __init__(self, config: Config):
        self._config = config
        self._project_path = config.project_path

    def create_provider(self, model: str) -> LiteLLMProvider:
        prov_cfg = self._config.get_provider(model)
        if not prov_cfg:
            return LiteLLMProvider()
        cred = self._config.get_credential(prov_cfg.credential)
        return LiteLLMProvider(
            api_key=cred.key if cred else "",
            api_base=prov_cfg.base_url or None,
            extra_headers=prov_cfg.request_headers or None,
        )

    def create_storage(self, public_url: str):
        if self._config.storage.type == "s3" and self._config.storage.s3_bucket:
            from openbotx.storage.s3 import S3Storage

            cred = self._config.get_credential(self._config.storage.credential)
            return S3Storage(
                bucket=self._config.storage.s3_bucket,
                region=self._config.storage.s3_region,
                access_key=cred.access_key if cred else "",
                secret_key=cred.secret_key if cred else "",
            )

        from openbotx.storage.local import LocalStorage

        return LocalStorage(base_path=self._project_path, public_url=public_url)

    def create_cron_callback(self, bus: MessageBus):
        async def _on_job(job: CronJob) -> None:
            chat_id = f"cron-{job.id}-{uuid4().hex[:6]}"
            msg = InboundMessage(
                channel="cron",
                sender_id="cron",
                chat_id=chat_id,
                content=job.payload.message,
                metadata={"cron_job_id": job.id, "cron_job_name": job.name},
            )
            await bus.publish_inbound(msg)

        return _on_job

    def create_orchestrator(
        self,
        bus: MessageBus,
        project_ctx: ProjectContext,
        dispatcher: EventDispatcher,
        task_manager: TaskManager,
        session_manager: SessionManager,
        project_path: Path,
        cron_service: CronService,
    ) -> Orchestrator:
        agent_loops: dict[str, AgentLoop] = {}
        default_agent_name = next(iter(self._config.agents))

        for name, agent_cfg in self._config.agents.items():
            agent_cfg.name = name
            prov_cfg = self._config.get_provider(agent_cfg.model)
            provider = self.create_provider(agent_cfg.model)

            if prov_cfg and prov_cfg.model_params:
                agent_cfg.model_params = {**prov_cfg.model_params, **agent_cfg.model_params}

            agent_workspace = agent_cfg.resolve_workspace(self._project_path)
            agent_workspace.mkdir(parents=True, exist_ok=True)

            agent_skills = SkillsLoader(project_path, agent_workspace)

            subagent_mgr = SubagentManager(
                provider=provider,
                agent_cfg=agent_cfg,
                project_ctx=project_ctx,
                bus=bus,
                task_manager=task_manager,
            )

            loop = AgentLoop(
                agent_cfg=agent_cfg,
                project_ctx=project_ctx,
                bus=bus,
                provider=provider,
                dispatcher=dispatcher,
                task_manager=task_manager,
                session_manager=session_manager,
                skills_loader=agent_skills,
                subagent_manager=subagent_mgr,
                cron_service=cron_service,
            )
            agent_loops[name] = loop

        classifier = None
        if len(agent_loops) > 1:
            agents_info = {name: cfg.description for name, cfg in self._config.agents.items()}
            classifier_model = (
                self._config.classifier.model or self._config.agents[default_agent_name].model
            )
            classifier_provider = self.create_provider(classifier_model)
            classifier = AgentClassifier(
                provider=classifier_provider,
                agents=agents_info,
                model=classifier_model,
            )

        # use max_concurrent from the default agent's params
        default_cfg = self._config.agents[default_agent_name]
        max_concurrent = default_cfg.agent_params.max_concurrent

        return Orchestrator(
            bus=bus,
            agents=agent_loops,
            classifier=classifier,
            default_agent=default_agent_name,
            session_manager=session_manager,
            max_concurrent=max_concurrent,
        )

    @staticmethod
    def setup_logging(project_path: Path) -> None:
        log_dir = project_path / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        root = logging.getLogger("openbotx")
        root.setLevel(logging.DEBUG)

        file_handler = logging.handlers.RotatingFileHandler(
            log_dir / "openbotx.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        root.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        root.addHandler(console_handler)


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = load_config()
    factory = ServerFactory(config)
    project_path = config.project_path
    system_workspace = config.workspace_path
    system_workspace.mkdir(parents=True, exist_ok=True)

    ServerFactory.setup_logging(project_path)

    from openbotx.config.schema import CredentialConfig

    # resolve server credential for JWT signing — create default if missing
    defaults_created = False
    server_cred = config.get_credential(config.server.credential)
    if not server_cred:
        server_cred = CredentialConfig(type="simple", key=uuid4().hex)
        config.credentials["server"] = server_cred
        config.server.credential = "server"
        defaults_created = True
        logger.info("Created default server credential for JWT signing")

    app.state.auth_secret = server_cred.key or uuid4().hex

    # resolve web_client credential for login — create default if missing
    wc_cred = config.get_credential(config.web_client.credential)
    if not wc_cred:
        wc_cred = CredentialConfig(type="login", username="admin", password="admin")
        config.credentials["web_client"] = wc_cred
        config.web_client.credential = "web_client"
        defaults_created = True
        logger.info("Created default web_client credential (admin/admin)")

    if defaults_created:
        save_config(config, config._config_path)

    app.state.auth_config = wc_cred

    ws_manager = WebSocketManager()
    dispatcher = EventDispatcher()
    dispatcher.add_handler(ws_manager)

    bus = MessageBus()
    session_manager = SessionManager(system_workspace)
    task_manager = TaskManager(system_workspace, dispatcher)
    skills_loader = SkillsLoader(project_path, system_workspace)
    cron_service = CronService(system_workspace, on_job_callback=factory.create_cron_callback(bus))

    public_dir = project_path / "public"
    public_dir.mkdir(parents=True, exist_ok=True)
    (public_dir / "media").mkdir(parents=True, exist_ok=True)
    (public_dir / "documents").mkdir(parents=True, exist_ok=True)

    public_url = config.server.public_url or f"http://localhost:{config.server.port}"
    storage = factory.create_storage(public_url)

    project_ctx = ProjectContext(
        project_path=project_path,
        public_dir=public_dir,
        public_url=public_url,
        tools=config.tools,
        image=config.image,
        credentials=config.credentials,
        providers=config.providers,
        storage=storage,
    )

    orchestrator = factory.create_orchestrator(
        bus=bus,
        project_ctx=project_ctx,
        dispatcher=dispatcher,
        task_manager=task_manager,
        session_manager=session_manager,
        project_path=project_path,
        cron_service=cron_service,
    )

    channel_manager = ChannelManager(
        config.channels,
        bus,
        storage=storage,
        dispatcher=dispatcher,
        credentials=config.credentials,
    )

    heartbeat = HeartbeatService(
        workspace=system_workspace,
        bus=bus,
        interval=config.heartbeat.interval,
        enabled=config.heartbeat.enabled,
    )

    app.state.config = config
    app.state.project_path = project_path
    app.state.storage = storage
    app.state.ws_manager = ws_manager
    app.state.dispatcher = dispatcher
    app.state.bus = bus
    app.state.session_manager = session_manager
    app.state.task_manager = task_manager
    app.state.skills_loader = skills_loader
    app.state.cron_service = cron_service
    app.state.orchestrator = orchestrator
    app.state.channel_manager = channel_manager
    app.state.heartbeat = heartbeat

    orchestrator_task = asyncio.create_task(orchestrator.run())
    cron_task = asyncio.create_task(cron_service.run())
    await channel_manager.start()
    await heartbeat.start()

    # re-queue tasks that were interrupted by previous shutdown
    for task in task_manager.get_recovered_tasks():
        msg = InboundMessage(
            channel=task.channel or "web",
            sender_id="system",
            chat_id=task.chat_id or "direct",
            content=task.description,
            metadata={"task_id": task.id, "recovered": True},
        )
        await bus.publish_inbound(msg)

    if config.server.public_url:
        logger.info(
            "openbotx %s started (workspace: %s, public_url: %s)",
            __version__,
            system_workspace,
            config.server.public_url,
        )
    else:
        logger.info("openbotx %s started (workspace: %s)", __version__, system_workspace)

    yield

    await heartbeat.stop()
    await orchestrator.stop()
    orchestrator_task.cancel()
    try:
        await orchestrator_task
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
        agents,
        auth,
        channels,
        chat,
        config,
        credentials,
        files,
        forms,
        marketplace,
        providers,
        scheduler,
        skills,
        system,
        tasks,
        tools,
    )

    app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
    app.include_router(system.router, prefix="/api", tags=["system"])
    app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
    app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
    app.include_router(files.router, prefix="/api/files", tags=["files"])
    app.include_router(skills.router, prefix="/api/skills", tags=["skills"])
    app.include_router(tools.router, prefix="/api/tools", tags=["tools"])
    app.include_router(channels.router, prefix="/api/channels", tags=["channels"])
    app.include_router(providers.router, prefix="/api/providers", tags=["providers"])
    app.include_router(credentials.router, prefix="/api/credentials", tags=["credentials"])
    app.include_router(scheduler.router, prefix="/api/scheduler", tags=["scheduler"])
    app.include_router(config.router, prefix="/api/config", tags=["config"])
    app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
    app.include_router(forms.router, prefix="/api/forms", tags=["forms"])
    app.include_router(marketplace.router, prefix="/api/marketplace", tags=["marketplace"])

    app.add_api_websocket_route("/ws", websocket_endpoint)

    @app.get("/public/{path:path}")
    async def serve_public(path: str):
        public_base = app.state.config.project_path / "public"
        try:
            file_path = (public_base / path).resolve()
            file_path.relative_to(public_base.resolve())
        except ValueError:
            return JSONResponse({"error": "Access denied"}, status_code=403)
        if file_path.is_file():
            return FileResponse(file_path)
        return JSONResponse({"error": "Not found"}, status_code=404)

    @app.get("/")
    async def root_redirect():
        return RedirectResponse("/app/")

    if WEB_CLIENT_DIR.is_dir():

        @app.get("/app/{path:path}")
        async def spa_fallback(path: str):
            try:
                file_path = (WEB_CLIENT_DIR / path).resolve()
                file_path.relative_to(WEB_CLIENT_DIR.resolve())
            except ValueError:
                return JSONResponse({"error": "Access denied"}, status_code=403)
            if file_path.is_file():
                return FileResponse(file_path)
            return FileResponse(WEB_CLIENT_DIR / "index.html")

    return app


app = create_app()
