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


class ConfigBatch(BaseModel):
    sections: dict[str, dict]


@router.patch("")
async def update_batch(body: ConfigBatch, request: Request):
    """Update multiple config sections in a single call."""
    from openbotx.config.loader import save_config

    config = request.app.state.config
    for section, data in body.sections.items():
        _apply_section(config, section, data)
    save_config(config, config._config_path)
    return {"status": "ok"}


@router.put("/{section}")
async def update_section(section: str, body: ConfigSection, request: Request):
    from openbotx.config.loader import save_config

    config = request.app.state.config

    if section == "advanced":
        yaml_str = body.data.get("yaml")
        if yaml_str:
            return await _save_advanced_yaml(yaml_str, config)

        for sect_name, sect_data in body.data.items():
            if isinstance(sect_data, dict):
                _apply_section(config, sect_name, sect_data)
        save_config(config, config._config_path)
        return {"status": "ok"}

    valid_sections = [
        "bot",
        "server",
        "agents",
        "image",
        "web_client",
        "tools",
        "storage",
        "cron",
        "providers",
        "credentials",
    ]
    if section not in valid_sections:
        return {"error": f"Invalid section: {section}"}

    _apply_section(config, section, body.data)
    save_config(config, config._config_path)
    return {"status": "ok"}


def _apply_section(config, section: str, data: dict) -> None:
    """Apply data to a single config section."""
    if not hasattr(config, section) or section.startswith("_"):
        return
    if section == "agents":
        _update_agents(config, data)
    elif section == "providers":
        _update_providers(config, data)
    elif section == "credentials":
        _update_credentials(config, data)
    else:
        current = getattr(config, section)
        _update_section(current, data)


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
        elif sect_name == "credentials" and isinstance(sect_data, dict):
            _update_credentials(config, sect_data)
        elif isinstance(sect_data, dict):
            current = getattr(config, sect_name, None)
            if current is not None:
                _update_section(current, sect_data)

    save_config(config, config._config_path)
    return {"status": "ok"}


def _update_section(current, data: dict) -> None:
    """Update a config section, preserving sensitive fields when masked or empty."""
    from pydantic import BaseModel

    for key, value in data.items():
        if not hasattr(current, key):
            continue
        if isinstance(value, dict):
            nested = getattr(current, key)
            if isinstance(nested, BaseModel):
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
            if key == "agent_params" and isinstance(value, dict):
                for pk, pv in value.items():
                    if hasattr(agent.agent_params, pk):
                        setattr(agent.agent_params, pk, pv)
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
        credential = pdata.get("credential", "")
        if not credential and existing:
            credential = existing.credential
        request_headers = pdata.get("request_headers", existing.request_headers if existing else {})
        request_options = pdata.get("request_options", existing.request_options if existing else {})
        model_params = pdata.get("model_params", existing.model_params if existing else {})
        config.providers[name] = ProviderConfig(
            name=name,
            credential=credential,
            request_headers=request_headers,
            request_options=request_options,
            model_params=model_params,
        )


def _update_credentials(config, data):
    from openbotx.config.schema import CredentialConfig

    for name, pdata in data.items():
        if not isinstance(pdata, dict):
            continue
        existing = config.credentials.get(name)
        if existing:
            for key, value in pdata.items():
                if not hasattr(existing, key):
                    continue
                if is_sensitive_key(key) and is_masked_or_empty(value):
                    continue
                setattr(existing, key, value)
        else:
            config.credentials[name] = CredentialConfig(**pdata)


@router.post("/restart")
async def restart_services(request: Request):
    from openbotx.agent.skills import SkillsLoader
    from openbotx.channels.manager import ChannelManager
    from openbotx.cron.service import CronService

    app = request.app
    config = app.state.config

    for name, service in [
        ("heartbeat", app.state.heartbeat),
        ("orchestrator", app.state.orchestrator),
        ("channel_manager", app.state.channel_manager),
        ("cron_service", app.state.cron_service),
    ]:
        if service is None:
            continue
        try:
            await service.stop()
        except Exception as e:
            logger.warning("Error stopping %s: %s", name, e)

    from openbotx.config.project import ProjectContext
    from openbotx.server.app import ServerFactory

    factory = ServerFactory(config)

    # re-resolve auth on restart
    server_cred = config.get_credential(config.server.credential)
    if server_cred:
        app.state.auth_secret = server_cred.key
    wc_cred = config.get_credential(config.web_client.credential)
    if wc_cred:
        app.state.auth_config = wc_cred

    workspace = config.workspace_path
    public_dir = config.project_path / "public"
    public_dir.mkdir(parents=True, exist_ok=True)
    (public_dir / "media").mkdir(parents=True, exist_ok=True)
    (public_dir / "documents").mkdir(parents=True, exist_ok=True)
    public_url = config.server.public_url or f"http://localhost:{config.server.port}"

    storage = factory.create_storage(public_url)
    app.state.storage = storage

    project_ctx = ProjectContext(
        project_path=config.project_path,
        public_dir=public_dir,
        public_url=public_url,
        tools=config.tools,
        image=config.image,
        credentials=config.credentials,
        providers=config.providers,
        storage=storage,
    )

    bus = app.state.bus
    dispatcher = app.state.dispatcher
    task_manager = app.state.task_manager
    session_manager = app.state.session_manager

    skills_loader = SkillsLoader(workspace)
    app.state.skills_loader = skills_loader

    cron_service = CronService(workspace, on_job_callback=factory.create_cron_callback(bus))
    app.state.cron_service = cron_service
    asyncio.create_task(cron_service.run())

    orchestrator = factory.create_orchestrator(
        bus=bus,
        project_ctx=project_ctx,
        dispatcher=dispatcher,
        task_manager=task_manager,
        session_manager=session_manager,
        skills_loader=skills_loader,
        cron_service=cron_service,
    )
    app.state.orchestrator = orchestrator
    asyncio.create_task(orchestrator.run())

    channel_manager = ChannelManager(
        config.channels,
        bus,
        storage=storage,
        dispatcher=dispatcher,
        credentials=config.credentials,
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
