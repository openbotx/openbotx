from dataclasses import dataclass


@dataclass(frozen=True)
class RequestContext:
    """Per-request context passed to tools during execution.

    Replaces the mutable set_context() pattern on tool instances,
    making concurrent message processing safe.
    """

    channel: str = ""
    chat_id: str = ""
    task_id: str = ""
    agent_name: str = ""
    message_id: str | None = None
