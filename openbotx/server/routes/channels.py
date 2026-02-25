from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter()


class ChannelUpdate(BaseModel):
    config: dict


@router.get("")
async def list_channels(request: Request):
    channel_manager = request.app.state.channel_manager
    return channel_manager.get_status()


@router.get("/{name}")
async def get_channel(name: str, request: Request):
    config = request.app.state.config
    if name == "telegram":
        return {
            "name": "telegram",
            "enabled": config.channels.telegram.enabled,
            "token": "***" if config.channels.telegram.token else "",
            "allowed_users": config.channels.telegram.allowed_users,
        }
    return {"error": f"Unknown channel: {name}"}


@router.put("/{name}")
async def update_channel(name: str, body: ChannelUpdate, request: Request):
    from openbotx.config.loader import save_config

    config = request.app.state.config
    if name == "telegram":
        tg = config.channels.telegram
        if "enabled" in body.config:
            tg.enabled = body.config["enabled"]
        if "token" in body.config:
            tg.token = body.config["token"]
        if "allowed_users" in body.config:
            tg.allowed_users = body.config["allowed_users"]
        save_config(config, config._config_path)
        return {"status": "ok"}
    return {"error": f"Unknown channel: {name}"}


@router.post("/{name}/start")
async def start_channel(name: str, request: Request):
    channel_manager = request.app.state.channel_manager
    try:
        started = await channel_manager.start_channel(name)
        if not started:
            return JSONResponse(
                {"error": "Channel already running or not available"}, status_code=409
            )
        return {"status": "started"}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/{name}/stop")
async def stop_channel(name: str, request: Request):
    channel_manager = request.app.state.channel_manager
    try:
        stopped = await channel_manager.stop_channel(name)
        if not stopped:
            return JSONResponse({"error": "Channel not running"}, status_code=409)
        return {"status": "stopped"}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
