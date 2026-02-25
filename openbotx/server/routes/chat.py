from fastapi import APIRouter, Request
from pydantic import BaseModel

from openbotx.bus.events import InboundMessage

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: str = "direct"


@router.post("")
async def send_message(req: ChatRequest, request: Request):
    bus = request.app.state.bus
    task_manager = request.app.state.task_manager

    key = _resolve_session_key(req.session_id)
    if ":" in key:
        channel, chat_id = key.split(":", 1)
    else:
        channel, chat_id = "web", key

    task = await task_manager.create_task(
        title=req.message[:80],
        description=req.message,
        channel=channel,
        chat_id=chat_id,
    )

    msg = InboundMessage(
        channel=channel,
        sender_id="web_user",
        chat_id=chat_id,
        content=req.message,
        metadata={"task_id": task.id},
    )
    await bus.publish_inbound(msg)

    return {"task_id": task.id, "session_id": req.session_id}


@router.get("/sessions")
async def list_sessions(request: Request):
    session_manager = request.app.state.session_manager
    return session_manager.list_sessions()


def _resolve_session_key(session_id: str) -> str:
    """Resolve a session_id to its internal session key.

    Keys that contain ':' are used as-is (e.g. 'web:abc123', 'heartbeat:heartbeat').
    Plain IDs are prefixed with 'web:' (standard user sessions).
    """
    if ":" in session_id:
        return session_id
    return f"web:{session_id}"


@router.get("/sessions/{session_id:path}")
async def get_session(session_id: str, request: Request):
    session_manager = request.app.state.session_manager
    key = _resolve_session_key(session_id)
    session = session_manager.get_or_create(key)
    return {
        "key": session.key,
        "messages": session.get_history(),
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
    }


@router.delete("/sessions/{session_id:path}")
async def delete_session(session_id: str, request: Request):
    session_manager = request.app.state.session_manager
    key = _resolve_session_key(session_id)
    session_manager.delete(key)
    return {"status": "deleted"}
