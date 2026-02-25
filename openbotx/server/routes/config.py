import asyncio
import logging

import yaml
from fastapi import APIRouter, Request
from pydantic import BaseModel

from openbotx.helpers.secrets import is_masked_or_empty, is_sensitive_key, mask_dict

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("")
async def get_config(request: Request):
    config = request.app.state.config
    raw = config.model_dump()
    return mask_dict(raw)


@router.get("/yaml")
async def get_config_yaml(request: Request):
    config = request.app.state.config
    raw = config.model_dump(mode="json")
    masked = mask_dict(raw)
    return {"yaml": yaml.safe_dump(masked, default_flow_style=False, sort_keys=False)}


class ConfigSection(BaseModel):
    data: dict


class YamlBody(BaseModel):
    yaml: str


@router.post("/validate")
async def validate_config(body: YamlBody):
    from openbotx.config.schema import Config

    try:
        data = yaml.safe_load(body.yaml)
        if not isinstance(data, dict):
            return {"valid": False, "error": "YAML must be a mapping"}
        Config.model_validate(data)
        return {"valid": True}
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        return {"valid": False, "error": str(e), "line": mark.line + 1 if mark else None}
    except Exception as e:
        return {"valid": False, "error": str(e)}


@router.put("/{section}")
async def update_section(section: str, body: ConfigSection, request: Request):
    from openbotx.config.loader import save_config

    config = request.app.state.config

    if section == "advanced":
        yaml_str = body.data.get("yaml")
        if yaml_str:
            return await _save_advanced_yaml(yaml_str, config)

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
        _update_section(current, body.data)

    save_config(config, config._config_path)
    return {"status": "ok"}


async def _save_advanced_yaml(yaml_str: str, config):
    from openbotx.config.loader import save_config
    from openbotx.config.schema import Config

    try:
        data = yaml.safe_load(yaml_str)
        if not isinstance(data, dict):
            return {"error": "YAML must be a mapping"}
        Config.model_validate(data)
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        return {"error": str(e), "line": mark.line + 1 if mark else None}
    except Exception as e:
        return {"error": str(e)}

    for sect_name, sect_data in data.items():
        if not hasattr(config, sect_name) or sect_name.startswith("_"):
            continue
        if sect_name == "agents" and isinstance(sect_data, dict):
            _update_agents(config, sect_data)
        elif sect_name == "providers" and isinstance(sect_data, dict):
            _update_providers(config, sect_data)
        elif isinstance(sect_data, dict):
            current = getattr(config, sect_name, None)
            if current is not None:
                _update_section(current, sect_data)

    save_config(config, config._config_path)
    return {"status": "ok"}


def _update_section(current, data: dict) -> None:
    """Update a config section, preserving sensitive fields when masked or empty."""
    for key, value in data.items():
        if not hasattr(current, key):
            continue
        if isinstance(value, dict):
            nested = getattr(current, key)
            if hasattr(nested, "__dict__"):
                _update_section(nested, value)
            else:
                setattr(current, key, value)
            continue
        if is_sensitive_key(key) and is_masked_or_empty(value):
            continue
        setattr(current, key, value)


def _update_agents(config, data):
    from openbotx.config.schema import AgentConfig

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
        if is_masked_or_empty(api_key):
            api_key = existing.api_key if existing else ""
        api_base = pdata.get("api_base") or (existing.api_base if existing else None)
        headers = pdata.get("headers", existing.headers if existing else {})
        options = pdata.get("options", existing.options if existing else {})
        config.providers[name] = ProviderConfig(
            api_key=api_key,
            api_base=api_base,
            headers=headers,
            options=options,
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

    for name, service in [
        ("heartbeat", getattr(app.state, "heartbeat", None)),
        ("agent_loop", app.state.agent_loop),
        ("channel_manager", app.state.channel_manager),
        ("cron_service", app.state.cron_service),
    ]:
        if service is None:
            continue
        try:
            await service.stop()
        except Exception as e:
            logger.warning("Error stopping %s: %s", name, e)

    workspace = config.workspace_path
    public_dir = config.project_path / "public"
    public_dir.mkdir(parents=True, exist_ok=True)
    (public_dir / "media").mkdir(parents=True, exist_ok=True)
    public_url = config.server.public_url or f"http://localhost:{config.server.port}"

    from openbotx.server.app import _create_storage

    storage = _create_storage(config, config.project_path, public_url)
    app.state.storage = storage

    bus = app.state.bus
    ws_manager = app.state.ws_manager
    task_manager = app.state.task_manager
    session_manager = app.state.session_manager

    provider_cfg = config.get_provider()
    provider = LiteLLMProvider(
        api_key=provider_cfg.api_key if provider_cfg else "",
        api_base=provider_cfg.api_base if provider_cfg else None,
        extra_headers=provider_cfg.headers if provider_cfg else None,
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
        image_config=config.image,
        storage=storage,
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
        storage=storage,
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

    channel_manager = ChannelManager(
        config.channels,
        bus,
        storage=storage,
        ws_manager=ws_manager,
    )
    app.state.channel_manager = channel_manager
    await channel_manager.start()

    from openbotx.heartbeat.service import HeartbeatService

    heartbeat = HeartbeatService(
        workspace=workspace,
        bus=bus,
        interval=config.heartbeat.interval,
        enabled=config.heartbeat.enabled,
    )
    app.state.heartbeat = heartbeat
    await heartbeat.start()

    logger.info("Services restarted successfully")
    return {"status": "restarted"}
