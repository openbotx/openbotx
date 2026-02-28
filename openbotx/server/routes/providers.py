from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from openbotx.providers.registry import PROVIDERS

router = APIRouter()


class ProviderUpdate(BaseModel):
    credential: str = ""
    base_url: str = ""
    request_headers: dict[str, str] = Field(default_factory=dict)
    request_options: dict = Field(default_factory=dict)
    model_params: dict = Field(default_factory=dict)


@router.get("")
async def list_providers(request: Request):
    config = request.app.state.config
    result = []
    for spec in PROVIDERS:
        configured = spec.name in config.providers
        cfg = config.providers.get(spec.name)
        cred = config.get_credential(cfg.credential) if cfg else None
        result.append(
            {
                "name": spec.name,
                "configured": configured,
                "credential": cfg.credential if configured else "",
                "has_key": bool(cred and cred.key) if configured else False,
                "base_url": cfg.base_url if configured else "",
                "request_headers": dict(cfg.request_headers) if configured else {},
                "request_options": dict(cfg.request_options) if configured else {},
                "model_params": cfg.model_params if configured else {},
            }
        )
    return result


@router.put("/{name}")
async def update_provider(name: str, body: ProviderUpdate, request: Request):
    from openbotx.config.loader import save_config
    from openbotx.config.schema import ProviderConfig

    config = request.app.state.config
    if name not in [s.name for s in PROVIDERS]:
        return {"error": f"Unknown provider: {name}"}

    existing = config.providers.get(name)
    credential = body.credential or (existing.credential if existing else "")

    config.providers[name] = ProviderConfig(
        name=name,
        credential=credential,
        base_url=body.base_url,
        request_headers=body.request_headers,
        request_options=body.request_options,
        model_params=body.model_params,
    )
    save_config(config, config._config_path)
    return {"status": "ok"}
