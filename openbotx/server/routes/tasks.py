from datetime import datetime, timedelta

from fastapi import APIRouter, Request
from pydantic import BaseModel

from openbotx.tasks.models import TaskState

router = APIRouter()

STALE_RETENTION = timedelta(hours=24)


class TaskUpdate(BaseModel):
    state: str


@router.get("")
async def list_tasks(request: Request):
    task_manager = request.app.state.task_manager
    cutoff = (datetime.now() - STALE_RETENTION).isoformat()
    tasks = []
    for t in task_manager.list_tasks():
        if t.state in (TaskState.TODO, TaskState.DONE, TaskState.ERROR) and t.updated_at < cutoff:
            continue
        tasks.append(t.to_dict())
    return tasks


@router.get("/{task_id}")
async def get_task(task_id: str, request: Request):
    task_manager = request.app.state.task_manager
    task = task_manager.get_task(task_id)
    if not task:
        return {"error": "Task not found"}
    return task.to_dict()


@router.patch("/{task_id}")
async def update_task(task_id: str, body: TaskUpdate, request: Request):
    task_manager = request.app.state.task_manager
    try:
        state = TaskState(body.state)
    except ValueError:
        return {"error": f"Invalid state: {body.state}"}

    task = await task_manager.update_state(task_id, state)
    if not task:
        return {"error": "Task not found"}
    return task.to_dict()
