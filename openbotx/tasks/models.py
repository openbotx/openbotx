from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class TaskState(str, Enum):
    TODO = "TODO"
    DOING = "DOING"
    DONE = "DONE"
    ERROR = "ERROR"


@dataclass
class Task:
    id: str
    title: str
    description: str = ""
    state: TaskState = TaskState.TODO
    agent_type: str = "agent"
    parent_task_id: str | None = None
    subagent_ids: list[str] = field(default_factory=list)
    result: str | None = None
    error: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "state": self.state.value,
            "agent_type": self.agent_type,
            "parent_task_id": self.parent_task_id,
            "subagent_ids": self.subagent_ids,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
