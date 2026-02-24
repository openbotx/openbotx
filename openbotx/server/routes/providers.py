from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from openbotx.providers.registry import PROVIDERS

router = APIRouter()


class ProviderUpdate(BaseModel):
    api_key: str = ""
    api_base: str = ""
    params: dict[str, str] = Field(default_factory=dict)


@router.get("")
async def list_providers(request: Request):
    config = request.app.state.config
    result = []
    for spec in PROVIDERS:
        configured = spec.name in config.providers
        cfg = config.providers.get(spec.name)
        result.append({
            "name": spec.name,
            "configured": configured,
            "api_base": cfg.api_base if configured else "",
            "has_key": bool(cfg.api_key) if configured else False,
            "params": dict(cfg.params) if configured else {},
        })
    return result


@router.put("/{name}")
async def update_provider(name: str, body: ProviderUpdate, request: Request):
    from openbotx.config.loader import save_config
    from openbotx.config.schema import ProviderConfig

    config = request.app.state.config
    if name not in [s.name for s in PROVIDERS]:
        return {"error": f"Unknown provider: {name}"}

    existing = config.providers.get(name)
    api_key = body.api_key or (existing.api_key if existing else "")
    api_base = body.api_base or (existing.api_base if existing else None)

    config.providers[name] = ProviderConfig(
        api_key=api_key,
        api_base=api_base,
        params=body.params,
    )
    save_config(config, config._config_path)
    return {"status": "ok"}
