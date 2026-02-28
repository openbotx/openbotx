from fastapi import APIRouter, Request
from pydantic import BaseModel

from openbotx.helpers.secrets import is_empty_or_blank, is_sensitive_key, mask_dict

router = APIRouter()


class CredentialBody(BaseModel):
    name: str
    data: dict


@router.get("")
async def list_credentials(request: Request):
    config = request.app.state.config
    result = {}
    for name, cred in config.credentials.items():
        raw = cred.model_dump()
        result[name] = mask_dict(raw)
    return result


@router.post("")
async def create_credential(body: CredentialBody, request: Request):
    from openbotx.config.loader import save_config
    from openbotx.config.schema import CredentialConfig

    config = request.app.state.config
    if body.name in config.credentials:
        return {"error": f"Credential already exists: {body.name}"}

    config.credentials[body.name] = CredentialConfig(**body.data)
    save_config(config, config._config_path)
    return {"status": "ok"}


@router.put("/{name}")
async def update_credential(name: str, body: dict, request: Request):
    from openbotx.config.loader import save_config

    config = request.app.state.config
    existing = config.credentials.get(name)
    if not existing:
        return {"error": f"Credential not found: {name}"}

    for key, value in body.items():
        if not hasattr(existing, key):
            continue
        if is_sensitive_key(key) and is_empty_or_blank(value):
            continue
        setattr(existing, key, value)

    save_config(config, config._config_path)
    return {"status": "ok"}


@router.delete("/{name}")
async def delete_credential(name: str, request: Request):
    from openbotx.config.loader import save_config

    config = request.app.state.config
    if name not in config.credentials:
        return {"error": f"Credential not found: {name}"}

    del config.credentials[name]
    save_config(config, config._config_path)
    return {"status": "ok"}
