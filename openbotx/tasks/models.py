from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class TaskState(StrEnum):
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
    agent_name: str = ""
    channel: str = ""
    chat_id: str = ""
    parent_task_id: str | None = None
    subagent_ids: list[str] = field(default_factory=list)
    result: str | None = None
    error: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: str | None = None
    completed_at: str | None = None
    tool_count: int = 0
    iteration_count: int = 0
    token_usage: dict = field(default_factory=dict)
    live_state: dict = field(default_factory=dict)

    @property
    def duration_ms(self) -> int | None:
        if not self.started_at:
            return None
        try:
            start = datetime.fromisoformat(self.started_at)
            end = datetime.fromisoformat(self.completed_at) if self.completed_at else datetime.now()
            return int((end - start).total_seconds() * 1000)
        except (ValueError, TypeError):
            return None

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "state": self.state.value,
            "agent_type": self.agent_type,
            "agent_name": self.agent_name,
            "channel": self.channel,
            "chat_id": self.chat_id,
            "parent_task_id": self.parent_task_id,
            "subagent_ids": self.subagent_ids,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "tool_count": self.tool_count,
            "iteration_count": self.iteration_count,
            "token_usage": self.token_usage,
            "duration_ms": self.duration_ms,
        }
        if self.live_state:
            d["live_state"] = self.live_state
        return d
