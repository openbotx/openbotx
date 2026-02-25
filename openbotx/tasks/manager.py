from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from openbotx.server.websocket import WebSocketManager
from openbotx.tasks.models import Task, TaskState

logger = logging.getLogger(__name__)


class TaskManager:
    """CRUD for tasks with WebSocket broadcasting on state changes."""

    def __init__(self, workspace: Path, ws_manager: WebSocketManager | None = None):
        self.store_path = workspace / "tasks.jsonl"
        self.ws_manager = ws_manager
        self._tasks: dict[str, Task] = {}
        self._recovered_ids: list[str] = []
        self._load()

    def _load(self) -> None:
        if not self.store_path.exists():
            return
        try:
            with open(self.store_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    task = Task(
                        id=data["id"],
                        title=data["title"],
                        description=data.get("description", ""),
                        state=TaskState(data.get("state", "TODO")),
                        agent_type=data.get("agent_type", "agent"),
                        channel=data.get("channel", ""),
                        chat_id=data.get("chat_id", ""),
                        parent_task_id=data.get("parent_task_id"),
                        subagent_ids=data.get("subagent_ids", []),
                        result=data.get("result"),
                        error=data.get("error"),
                        created_at=data.get("created_at", ""),
                        updated_at=data.get("updated_at", ""),
                    )
                    self._tasks[task.id] = task
        except Exception as e:
            logger.warning("failed to load tasks from %s: %s", self.store_path, e)

        # recover tasks that were interrupted mid-execution
        recovered = 0
        now = datetime.now()
        now_iso = now.isoformat()
        requeue_cutoff = (now - timedelta(hours=1)).isoformat()

        for task in self._tasks.values():
            if task.state == TaskState.DOING:
                task.updated_at = now_iso
                if task.agent_type == "subagent":
                    task.state = TaskState.ERROR
                    task.error = "interrupted by server shutdown"
                else:
                    task.state = TaskState.TODO
                    self._recovered_ids.append(task.id)
                recovered += 1
            elif task.state == TaskState.TODO and task.created_at > requeue_cutoff:
                # TODO tasks with no message in the queue (lost on shutdown)
                self._recovered_ids.append(task.id)
                recovered += 1

        if recovered:
            logger.info("recovered %d interrupted task(s)", recovered)
            self._persist()

    def get_recovered_tasks(self) -> list[Task]:
        """Return tasks recovered from DOING on startup and clear the list."""
        tasks = [self._tasks[tid] for tid in self._recovered_ids if tid in self._tasks]
        self._recovered_ids.clear()
        return tasks

    def _persist(self) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.store_path, "w", encoding="utf-8") as f:
            for task in self._tasks.values():
                f.write(json.dumps(task.to_dict(), ensure_ascii=False) + "\n")

    async def _broadcast(self, event_type: str, task: Task) -> None:
        if self.ws_manager:
            await self.ws_manager.broadcast(event_type, task.to_dict())

    async def create_task(
        self,
        title: str,
        description: str = "",
        agent_type: str = "agent",
        channel: str = "",
        chat_id: str = "",
        parent_task_id: str | None = None,
    ) -> Task:
        task = Task(
            id=str(uuid.uuid4())[:8],
            title=title,
            description=description,
            agent_type=agent_type,
            channel=channel,
            chat_id=chat_id,
            parent_task_id=parent_task_id,
        )
        self._tasks[task.id] = task

        if parent_task_id and parent_task_id in self._tasks:
            parent = self._tasks[parent_task_id]
            parent.subagent_ids.append(task.id)

        self._persist()
        await self._broadcast("task:created", task)
        return task

    async def update_state(
        self,
        task_id: str,
        state: TaskState,
        result: str | None = None,
        error: str | None = None,
    ) -> Task | None:
        task = self._tasks.get(task_id)
        if not task:
            return None

        task.state = state
        task.updated_at = datetime.now().isoformat()
        if result is not None:
            task.result = result
        if error is not None:
            task.error = error

        self._persist()
        await self._broadcast("task:updated", task)
        return task

    def get_task(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def list_tasks(self) -> list[Task]:
        return sorted(
            self._tasks.values(),
            key=lambda t: t.created_at,
            reverse=True,
        )
