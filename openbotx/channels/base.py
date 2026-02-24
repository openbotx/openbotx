from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable

from openbotx.bus.events import InboundMessage, OutboundMessage


class BaseChannel(ABC):
    """Abstract base class for chat channels."""

    def __init__(
        self,
        name: str,
        on_message: Callable[[InboundMessage], Awaitable[None]] | None = None,
        allow_from: list[str] | None = None,
    ):
        self.channel_name = name
        self._on_message = on_message
        self._allow_from = set(allow_from) if allow_from else set()
        self._running = False

    def set_message_handler(
        self, handler: Callable[[InboundMessage], Awaitable[None]]
    ) -> None:
        self._on_message = handler

    def is_allowed(self, sender_id: str) -> bool:
        if not self._allow_from:
            return True
        return sender_id in self._allow_from

    @property
    def is_running(self) -> bool:
        return self._running

    @abstractmethod
    async def start(self) -> None:
        pass

    @abstractmethod
    async def stop(self) -> None:
        pass

    @abstractmethod
    async def send(self, msg: OutboundMessage) -> None:
        pass
