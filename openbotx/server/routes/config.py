import asyncio
import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)


def _mask_keys(d) -> dict | list:
    if isinstance(d, list):
        return [_mask_keys(v) for v in d]
    if not isinstance(d, dict):
        return d
    masked = {}
    for k, v in d.items():
        if isinstance(v, (dict, list)):
            masked[k] = _mask_keys(v)
        elif "key" in k.lower() or "token" in k.lower() or "secret" in k.lower() or "password" in k.lower():
            masked[k] = "***" if v else ""
        else:
            masked[k] = v
    return masked


@router.get("")
async def get_config(request: Request):
    config = request.app.state.config
    raw = config.model_dump()
    return _mask_keys(raw)


class ConfigSection(BaseModel):
    data: dict


@router.put("/{section}")
async def update_section(section: str, body: ConfigSection, request: Request):
    from openbotx.config.loader import save_config
    from openbotx.config.schema import AgentConfig, ModelParams

    config = request.app.state.config

    if section == "advanced":
        for sect_name, sect_data in body.data.items():
            if not hasattr(config, sect_name) or sect_name.startswith("_"):
                continue
            if sect_name == "agents" and isinstance(sect_data, dict):
                _update_agents(config, sect_data)
            elif sect_name == "providers" and isinstance(sect_data, dict):
                _update_providers(config, sect_data)
            elif isinstance(sect_data, dict):
                current = getattr(config, sect_name, None)
                if current is not None:
                    for key, value in sect_data.items():
                        if hasattr(current, key):
                            setattr(current, key, value)
        save_config(config, config._config_path)
        return {"status": "ok"}

    valid_sections = ["bot", "server", "agents", "image", "auth", "tools", "storage", "cron"]
    if section not in valid_sections:
        return {"error": f"Invalid section: {section}"}

    if section == "agents":
        _update_agents(config, body.data)
    else:
        current = getattr(config, section)
        for key, value in body.data.items():
            if hasattr(current, key):
                setattr(current, key, value)

    save_config(config, config._config_path)
    return {"status": "ok"}


def _update_agents(config, data):
    from openbotx.config.schema import AgentConfig, ModelParams

    new_agents = {}
    for agent_name, agent_data in data.items():
        if not isinstance(agent_data, dict):
            continue
        if agent_name in config.agents:
            agent = config.agents[agent_name]
        else:
            agent = AgentConfig()

        for key, value in agent_data.items():
            if key == "params" and isinstance(value, dict):
                for pk, pv in value.items():
                    if hasattr(agent.params, pk):
                        setattr(agent.params, pk, pv)
            elif hasattr(agent, key):
                setattr(agent, key, value)

        new_agents[agent_name] = agent

    if "main" not in new_agents and "main" in config.agents:
        new_agents["main"] = config.agents["main"]

    config.agents = new_agents


def _update_providers(config, data):
    from openbotx.config.schema import ProviderConfig

    for name, pdata in data.items():
        if not isinstance(pdata, dict):
            continue
        existing = config.providers.get(name)
        api_key = pdata.get("api_key", "")
        if not api_key or api_key == "***":
            api_key = existing.api_key if existing else ""
        api_base = pdata.get("api_base") or (existing.api_base if existing else None)
        params = pdata.get("params", existing.params if existing else {})
        config.providers[name] = ProviderConfig(
            api_key=api_key,
            api_base=api_base,
            params=params,
        )


@router.post("/restart")
async def restart_services(request: Request):
    from openbotx.agent.loop import AgentLoop
    from openbotx.agent.skills import SkillsLoader
    from openbotx.agent.subagent import SubagentManager
    from openbotx.channels.manager import ChannelManager
    from openbotx.cron.service import CronService
    from openbotx.providers.litellm_provider import LiteLLMProvider

    app = request.app
    config = app.state.config

    try:
        await app.state.agent_loop.stop()
    except Exception as e:
        logger.warning("Error stopping agent loop: %s", e)

    try:
        await app.state.channel_manager.stop()
    except Exception as e:
        logger.warning("Error stopping channels: %s", e)

    try:
        await app.state.cron_service.stop()
    except Exception as e:
        logger.warning("Error stopping cron: %s", e)

    workspace = config.workspace_path
    bus = app.state.bus
    ws_manager = app.state.ws_manager
    task_manager = app.state.task_manager
    session_manager = app.state.session_manager

    provider_cfg = config.get_provider()
    provider = LiteLLMProvider(
        api_key=provider_cfg.api_key if provider_cfg else "",
        api_base=provider_cfg.api_base if provider_cfg else None,
    )
    app.state.provider = provider

    skills_loader = SkillsLoader(workspace)
    app.state.skills_loader = skills_loader

    main_agent = config.main_agent

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
    app.state.subagent_manager = subagent_manager

    agent_loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=workspace,
        ws_manager=ws_manager,
        task_manager=task_manager,
        session_manager=session_manager,
        skills_loader=skills_loader,
        subagent_manager=subagent_manager,
        cron_service=None,
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
    app.state.agent_loop = agent_loop
    asyncio.create_task(agent_loop.run())

    from openbotx.bus.events import InboundMessage
    from openbotx.cron.types import CronJob

    def _build_cron_callback():
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

    cron_service = CronService(workspace, on_job_callback=_build_cron_callback())
    app.state.cron_service = cron_service
    agent_loop._cron_service = cron_service
    asyncio.create_task(cron_service.run())

    channel_manager = ChannelManager(config.channels, bus, ws_manager=ws_manager)
    app.state.channel_manager = channel_manager
    await channel_manager.start()

    logger.info("Services restarted successfully")
    return {"status": "restarted"}
