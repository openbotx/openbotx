"""Browser relay server: HTTP + WebSocket bridge for the Chrome extension.

Compatible with the Chrome extension that attaches to tabs
and forwards CDP over WebSocket. The relay listens on 127.0.0.1:18792 by default;
the extension connects to ws://127.0.0.1:18792/extension, and CDP clients
(e.g. python-cdp via cdp_tool) connect to the same host and use /json/version
then ws://.../cdp.
"""

import asyncio
import json
from typing import Any

from aiohttp import web

from openbotx.helpers.logger import get_logger

logger = get_logger(__name__)

# Default port the extension expects (configurable in extension options)
DEFAULT_RELAY_PORT = 18792
DEFAULT_RELAY_HOST = "127.0.0.1"

# Shared relay state (one server per process)
_extension_ws: web.WebSocketResponse | None = None
_cdp_clients: set[web.WebSocketResponse] = set()
_connected_targets: dict[str, dict[str, Any]] = {}
_pending_extension: dict[int, asyncio.Future[Any]] = {}
_next_extension_id = 1
_extensions_lock = asyncio.Lock()


def _is_loopback(remote: str | None) -> bool:
    if not remote:
        return False
    if remote == "127.0.0.1":
        return True
    if remote.startswith("127."):
        return True
    if remote == "::1":
        return True
    if remote.startswith("::ffff:127."):
        return True
    return False


def _cdp_ws_url(host: str, port: int) -> str:
    return f"ws://{host}:{port}/cdp"


async def _send_to_extension(payload: dict[str, Any]) -> Any:
    global _extension_ws, _pending_extension, _next_extension_id
    ws = _extension_ws
    if not ws or ws.closed:
        raise ConnectionError("Chrome extension not connected")
    req_id = _next_extension_id
    _next_extension_id += 1
    payload["id"] = req_id
    fut: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
    _pending_extension[req_id] = fut
    try:
        await ws.send_str(json.dumps(payload))
        return await asyncio.wait_for(fut, timeout=30.0)
    finally:
        _pending_extension.pop(req_id, None)


def _broadcast_to_cdp(evt: dict[str, Any]) -> None:
    msg = json.dumps(evt)
    for ws in list(_cdp_clients):
        if not ws.closed:
            try:
                asyncio.create_task(_safe_send(ws, msg))
            except Exception:
                pass


async def _safe_send(ws: web.WebSocketResponse, msg: str) -> None:
    try:
        await ws.send_str(msg)
    except Exception:
        pass


def _send_response_to_cdp(ws: web.WebSocketResponse, res: dict[str, Any]) -> None:
    if ws.closed:
        return
    asyncio.create_task(_safe_send(ws, json.dumps(res)))


def _ensure_target_events_for_client(ws: web.WebSocketResponse, mode: str) -> None:
    for target in _connected_targets.values():
        if mode == "autoAttach":
            evt = {
                "method": "Target.attachedToTarget",
                "params": {
                    "sessionId": target["sessionId"],
                    "targetInfo": {**target["targetInfo"], "attached": True},
                    "waitingForDebugger": False,
                },
            }
        else:
            evt = {
                "method": "Target.targetCreated",
                "params": {"targetInfo": {**target["targetInfo"], "attached": True}},
            }
        asyncio.create_task(_safe_send(ws, json.dumps(evt)))


async def _route_cdp_command(cmd: dict[str, Any]) -> Any:
    method = cmd.get("method") or ""
    params = cmd.get("params") or {}
    session_id = cmd.get("sessionId")

    if method == "Browser.getVersion":
        return {
            "protocolVersion": "1.3",
            "product": "Chrome/OpenBotX-Extension-Relay",
            "revision": "0",
            "userAgent": "OpenBotX-Extension-Relay",
            "jsVersion": "V8",
        }
    if method == "Browser.setDownloadBehavior":
        return {}
    if method in ("Target.setAutoAttach", "Target.setDiscoverTargets"):
        return {}
    if method == "Target.getTargets":
        return {
            "targetInfos": [
                {**t["targetInfo"], "attached": True} for t in _connected_targets.values()
            ],
        }
    if method == "Target.getTargetInfo":
        target_id = (params or {}).get("targetId")
        if target_id:
            for t in _connected_targets.values():
                if t["targetId"] == target_id:
                    return {"targetInfo": t["targetInfo"]}
        if session_id and session_id in _connected_targets:
            t = _connected_targets[session_id]
            return {"targetInfo": t["targetInfo"]}
        first = next(iter(_connected_targets.values()), None)
        if first:
            return {"targetInfo": first["targetInfo"]}
        return {"targetInfo": {"targetId": "", "type": "page", "title": "", "url": ""}}
    if method == "Target.attachToTarget":
        target_id = (params or {}).get("targetId")
        if not target_id:
            raise ValueError("targetId required")
        for t in _connected_targets.values():
            if t["targetId"] == target_id:
                return {"sessionId": t["sessionId"]}
        raise ValueError("target not found")

    # Forward to extension
    return await _send_to_extension(
        {
            "method": "forwardCDPCommand",
            "params": {
                "method": method,
                "sessionId": session_id,
                "params": params,
            },
        }
    )


# ---- HTTP routes ----


async def _handle_root(request: web.Request) -> web.Response:
    if request.method == "HEAD":
        return web.Response(status=200)
    return web.Response(body=b"OK", content_type="text/plain")


async def _handle_extension_status(request: web.Request) -> web.Response:
    return web.json_response({"connected": _extension_ws is not None and not _extension_ws.closed})


async def _handle_json_version(request: web.Request) -> web.Response:
    host_header = (
        request.headers.get("Host", "").strip() or f"{DEFAULT_RELAY_HOST}:{DEFAULT_RELAY_PORT}"
    )
    if ":" in host_header:
        host, port_str = host_header.rsplit(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            port = DEFAULT_RELAY_PORT
    else:
        host = host_header
        port = DEFAULT_RELAY_PORT
    payload = {
        "Browser": "OpenBotX/extension-relay",
        "Protocol-Version": "1.3",
    }
    if _extension_ws and not _extension_ws.closed:
        payload["webSocketDebuggerUrl"] = _cdp_ws_url(host, port)
    return web.json_response(payload)


async def _handle_json_list(request: web.Request) -> web.Response:
    host_header = (
        request.headers.get("Host", "").strip() or f"{DEFAULT_RELAY_HOST}:{DEFAULT_RELAY_PORT}"
    )
    if ":" in host_header:
        host, port_str = host_header.rsplit(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            port = DEFAULT_RELAY_PORT
    else:
        host = host_header
        port = DEFAULT_RELAY_PORT
    cdp_url = _cdp_ws_url(host, port)
    list_data = [
        {
            "id": t["targetId"],
            "type": t["targetInfo"].get("type", "page"),
            "title": t["targetInfo"].get("title", ""),
            "description": t["targetInfo"].get("title", ""),
            "url": t["targetInfo"].get("url", ""),
            "webSocketDebuggerUrl": cdp_url,
            "devtoolsFrontendUrl": f"/devtools/inspector.html?ws={cdp_url.replace('ws://', '')}",
        }
        for t in _connected_targets.values()
    ]
    return web.json_response(list_data)


async def _handle_json_activate(request: web.Request) -> web.Response:
    target_id = request.match_info.get("targetId", "").strip()
    if not target_id:
        return web.Response(status=400, text="targetId required")
    try:
        await _send_to_extension(
            {
                "method": "forwardCDPCommand",
                "params": {
                    "method": "Target.activateTarget",
                    "params": {"targetId": target_id},
                },
            }
        )
    except Exception:
        pass
    return web.Response(text="OK")


async def _handle_json_close(request: web.Request) -> web.Response:
    target_id = request.match_info.get("targetId", "").strip()
    if not target_id:
        return web.Response(status=400, text="targetId required")
    try:
        await _send_to_extension(
            {
                "method": "forwardCDPCommand",
                "params": {
                    "method": "Target.closeTarget",
                    "params": {"targetId": target_id},
                },
            }
        )
    except Exception:
        pass
    return web.Response(text="OK")


# ---- WebSocket: /extension ----


async def _ws_extension(request: web.Request) -> web.WebSocketResponse:
    global _extension_ws
    peer = request.remote
    if not _is_loopback(peer):
        raise web.HTTPForbidden(text="Forbidden")
    if _extension_ws and not _extension_ws.closed:
        raise web.HTTPConflict(text="Extension already connected")

    ws = web.WebSocketResponse()
    await ws.prepare(request)
    _extension_ws = ws
    logger.info("extension_connected", peer=peer)

    ping_task: asyncio.Task[None] | None = None

    async def ping_loop() -> None:
        while not ws.closed:
            await asyncio.sleep(5)
            if ws.closed:
                break
            try:
                await ws.send_str(json.dumps({"method": "ping"}))
            except Exception:
                break

    try:
        ping_task = asyncio.create_task(ping_loop())
        while not ws.closed:
            try:
                raw = await ws.receive()
            except Exception:
                break
            if raw.type != web.WSMsgType.TEXT:
                if raw.type in (
                    web.WSMsgType.CLOSE,
                    web.WSMsgType.ERROR,
                    web.WSMsgType.CLOSED,
                ):
                    break
                continue
            try:
                msg = json.loads(raw.data)
            except json.JSONDecodeError:
                continue
            if not isinstance(msg, dict):
                continue

            # ping -> pong
            if msg.get("method") == "ping":
                try:
                    await ws.send_str(json.dumps({"method": "pong"}))
                except Exception:
                    pass
                continue

            # response to forwardCDPCommand
            if isinstance(msg.get("id"), (int, float)):
                req_id = int(msg["id"])
                if req_id in _pending_extension:
                    fut = _pending_extension.pop(req_id, None)
                    if fut and not fut.done():
                        if msg.get("error"):
                            fut.set_exception(Exception(str(msg["error"])))
                        else:
                            fut.set_result(msg.get("result"))
                continue

            # forwardCDPEvent
            if msg.get("method") != "forwardCDPEvent":
                continue
            params = msg.get("params") or {}
            evt_method = params.get("method")
            evt_params = params.get("params")
            evt_session_id = params.get("sessionId")
            if not evt_method:
                continue

            if evt_method == "Target.attachedToTarget":
                attached = evt_params or {}
                target_type = (attached.get("targetInfo") or {}).get("type", "page")
                if target_type != "page":
                    continue
                sid = attached.get("sessionId")
                target_info = attached.get("targetInfo") or {}
                tid = target_info.get("targetId")
                if sid and tid:
                    prev = _connected_targets.get(sid)
                    next_tid = tid
                    prev_tid = prev["targetId"] if prev else None
                    changed = bool(prev and prev_tid and prev_tid != next_tid)
                    _connected_targets[sid] = {
                        "sessionId": sid,
                        "targetId": next_tid,
                        "targetInfo": target_info,
                    }
                    if changed and prev_tid:
                        _broadcast_to_cdp(
                            {
                                "method": "Target.detachedFromTarget",
                                "params": {"sessionId": sid, "targetId": prev_tid},
                                "sessionId": sid,
                            }
                        )
                    if not prev or changed:
                        _broadcast_to_cdp(
                            {
                                "method": evt_method,
                                "params": evt_params,
                                "sessionId": sid,
                            }
                        )
                continue

            if evt_method == "Target.detachedFromTarget":
                detached = evt_params or {}
                if detached.get("sessionId"):
                    _connected_targets.pop(detached["sessionId"], None)
                _broadcast_to_cdp(
                    {
                        "method": evt_method,
                        "params": evt_params,
                        "sessionId": evt_session_id,
                    }
                )
                continue

            if evt_method == "Target.targetInfoChanged":
                changed = evt_params or {}
                target_info = changed.get("targetInfo") or {}
                tid = target_info.get("targetId")
                if tid and (target_info.get("type", "page") == "page"):
                    for sid, target in list(_connected_targets.items()):
                        if target["targetId"] != tid:
                            continue
                        _connected_targets[sid] = {
                            **target,
                            "targetInfo": {**target["targetInfo"], **target_info},
                        }
                _broadcast_to_cdp(
                    {
                        "method": evt_method,
                        "params": evt_params,
                        "sessionId": evt_session_id,
                    }
                )
                continue

            # All other events: broadcast to CDP clients
            _broadcast_to_cdp(
                {
                    "method": evt_method,
                    "params": evt_params,
                    "sessionId": evt_session_id,
                }
            )
    except Exception as e:
        logger.debug("extension_ws_error", error=str(e))
    finally:
        if ping_task and not ping_task.done():
            ping_task.cancel()
            try:
                await ping_task
            except asyncio.CancelledError:
                pass
        _extension_ws = None
        for fut in _pending_extension.values():
            if not fut.done():
                fut.set_exception(ConnectionError("extension disconnected"))
        _pending_extension.clear()
        _connected_targets.clear()
        for client in list(_cdp_clients):
            try:
                await client.close(code=1011, message="extension disconnected")
            except Exception:
                pass
        _cdp_clients.clear()
        logger.info("extension_disconnected", peer=peer)

    return ws


# ---- WebSocket: /cdp ----


async def _ws_cdp(request: web.Request) -> web.WebSocketResponse:
    peer = request.remote
    if not _is_loopback(peer):
        raise web.HTTPForbidden(text="Forbidden")
    if not _extension_ws or _extension_ws.closed:
        raise web.HTTPServiceUnavailable(text="Extension not connected")

    ws = web.WebSocketResponse()
    await ws.prepare(request)
    _cdp_clients.add(ws)
    logger.info("cdp_client_connected", peer=peer)

    try:
        while not ws.closed:
            try:
                raw = await ws.receive()
            except Exception:
                break
            if raw.type != web.WSMsgType.TEXT:
                if raw.type in (
                    web.WSMsgType.CLOSE,
                    web.WSMsgType.ERROR,
                    web.WSMsgType.CLOSED,
                ):
                    break
                continue
            try:
                cmd = json.loads(raw.data)
            except json.JSONDecodeError:
                continue
            if (
                not isinstance(cmd, dict)
                or not isinstance(cmd.get("id"), (int, float))
                or not isinstance(cmd.get("method"), str)
            ):
                continue

            cmd_id = int(cmd["id"])
            session_id = cmd.get("sessionId")

            if not _extension_ws or _extension_ws.closed:
                _send_response_to_cdp(
                    ws,
                    {
                        "id": cmd_id,
                        "sessionId": session_id,
                        "error": {"message": "Extension not connected"},
                    },
                )
                continue

            try:
                result = await _route_cdp_command(cmd)

                if cmd.get("method") == "Target.setAutoAttach" and not session_id:
                    _ensure_target_events_for_client(ws, "autoAttach")
                if cmd.get("method") == "Target.setDiscoverTargets":
                    discover = (cmd.get("params") or {}).get("discover")
                    if discover is True:
                        _ensure_target_events_for_client(ws, "discover")
                if cmd.get("method") == "Target.attachToTarget":
                    params = cmd.get("params") or {}
                    target_id = params.get("targetId")
                    if target_id:
                        for t in _connected_targets.values():
                            if t["targetId"] == target_id:
                                await _safe_send(
                                    ws,
                                    json.dumps(
                                        {
                                            "method": "Target.attachedToTarget",
                                            "params": {
                                                "sessionId": t["sessionId"],
                                                "targetInfo": {
                                                    **t["targetInfo"],
                                                    "attached": True,
                                                },
                                                "waitingForDebugger": False,
                                            },
                                        }
                                    ),
                                )
                                break  # one target matched

                _send_response_to_cdp(ws, {"id": cmd_id, "sessionId": session_id, "result": result})
            except Exception as e:
                _send_response_to_cdp(
                    ws,
                    {
                        "id": cmd_id,
                        "sessionId": session_id,
                        "error": {"message": str(e)},
                    },
                )
    except Exception as e:
        logger.debug("cdp_ws_error", error=str(e))
    finally:
        _cdp_clients.discard(ws)
        logger.info("cdp_client_disconnected", peer=peer)

    return ws


def create_relay_app(
    host: str = DEFAULT_RELAY_HOST, port: int = DEFAULT_RELAY_PORT
) -> web.Application:
    app = web.Application()
    # All routes only from loopback
    app.middlewares.append(_loopback_middleware)
    app.router.add_route("GET", "/", _handle_root)
    app.router.add_route("HEAD", "/", _handle_root)
    app.router.add_get("/extension/status", _handle_extension_status)
    app.router.add_get("/json/activate/{targetId}", _handle_json_activate)
    app.router.add_put("/json/activate/{targetId}", _handle_json_activate)
    app.router.add_get("/json/close/{targetId}", _handle_json_close)
    app.router.add_put("/json/close/{targetId}", _handle_json_close)
    app.router.add_get("/extension", _ws_extension)
    app.router.add_get("/cdp", _ws_cdp)

    for path in ("/json/version", "/json/version/"):
        app.router.add_get(path, _handle_json_version)
        app.router.add_put(path, _handle_json_version)

    for path in ("/json", "/json/", "/json/list", "/json/list/"):
        app.router.add_get(path, _handle_json_list)

    return app


@web.middleware
async def _loopback_middleware(request: web.Request, handler: Any) -> web.StreamResponse:
    if request.path.startswith("/") and not _is_loopback(request.remote):
        raise web.HTTPForbidden(text="Forbidden")
    return await handler(request)


async def run_relay_server(
    host: str = DEFAULT_RELAY_HOST,
    port: int = DEFAULT_RELAY_PORT,
) -> None:
    """Run the browser relay server (HTTP + WebSocket) until shutdown."""
    app = create_relay_app(host=host, port=port)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    logger.info("relay_started", host=host, port=port, url=f"http://{host}:{port}")
    # Keep running until cancelled
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        pass
    finally:
        await runner.cleanup()
