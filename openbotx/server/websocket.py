import json
import logging
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from openbotx.server.auth import verify_token

logger = logging.getLogger(__name__)


class WebSocketManager:

    def __init__(self):
        self._connections: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.add(ws)
        logger.info("WebSocket connected (%d total)", len(self._connections))

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.discard(ws)
        logger.info("WebSocket disconnected (%d total)", len(self._connections))

    async def broadcast(self, event_type: str, data: Any) -> None:
        if not self._connections:
            return
        msg = json.dumps({"type": event_type, "data": data}, default=str)
        dead: set[WebSocket] = set()
        for ws in self._connections:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.add(ws)
        self._connections -= dead

    @property
    def connection_count(self) -> int:
        return len(self._connections)


async def websocket_endpoint(websocket: WebSocket) -> None:
    secret = getattr(websocket.app.state, "auth_secret", "")
    if secret:
        token = websocket.query_params.get("token", "")
        payload = verify_token(token, secret)
        if not payload:
            await websocket.close(code=4001)
            return

    manager: WebSocketManager = websocket.app.state.ws_manager
    bus = websocket.app.state.bus

    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")

            if msg_type == "chat:send":
                from openbotx.bus.events import InboundMessage

                content = data.get("data", {}).get("message", "")
                session_id = data.get("data", {}).get("session_id", "direct")

                msg = InboundMessage(
                    channel="web",
                    sender_id="web_user",
                    chat_id=session_id,
                    content=content,
                    metadata=data.get("data", {}).get("metadata", {}),
                )
                await bus.publish_inbound(msg)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
