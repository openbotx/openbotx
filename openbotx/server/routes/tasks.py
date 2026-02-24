from fastapi import APIRouter, Request
from pydantic import BaseModel

from openbotx.tasks.models import TaskState

router = APIRouter()


class TaskUpdate(BaseModel):
    state: str


@router.get("")
async def list_tasks(request: Request):
    task_manager = request.app.state.task_manager
    return [t.to_dict() for t in task_manager.list_tasks()]


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
