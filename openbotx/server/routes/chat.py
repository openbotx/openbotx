from fastapi import APIRouter, Request
from pydantic import BaseModel

from openbotx.bus.events import InboundMessage
from openbotx.tasks.models import TaskState

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: str = "direct"


@router.post("")
async def send_message(req: ChatRequest, request: Request):
    bus = request.app.state.bus
    task_manager = request.app.state.task_manager

    task = await task_manager.create_task(
        title=req.message[:80],
        description=req.message,
    )

    msg = InboundMessage(
        channel="web",
        sender_id="web_user",
        chat_id=req.session_id,
        content=req.message,
        metadata={"task_id": task.id},
    )
    await bus.publish_inbound(msg)

    return {"task_id": task.id, "session_id": req.session_id}


@router.get("/sessions")
async def list_sessions(request: Request):
    session_manager = request.app.state.session_manager
    return session_manager.list_sessions()


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, request: Request):
    session_manager = request.app.state.session_manager
    session = session_manager.get_or_create(f"web:{session_id}")
    return {
        "key": session.key,
        "messages": session.get_history(),
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
    }


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, request: Request):
    session_manager = request.app.state.session_manager
    session_manager.delete(f"web:{session_id}")
    return {"status": "deleted"}
