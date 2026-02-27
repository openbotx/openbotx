import logging
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class EventHandler(Protocol):
    async def broadcast(self, event_type: str, data: Any) -> None: ...


class EventDispatcher:
    """Routes events to registered handlers.

    Components call the dispatcher instead of a specific transport
    (e.g. WebSocket).  This makes it easy to swap or add handlers
    without touching every caller.
    """

    def __init__(self) -> None:
        self._handlers: list[EventHandler] = []

    def add_handler(self, handler: EventHandler) -> None:
        self._handlers.append(handler)

    async def broadcast(self, event_type: str, data: Any) -> None:
        for handler in self._handlers:
            try:
                await handler.broadcast(event_type, data)
            except Exception:
                logger.exception("event handler error for %s", event_type)
