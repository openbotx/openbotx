import typing as t


class IEventLoop(t.Protocol):
    """Compatibility layer for the event loop."""

    async def sleep(self, delay: float) -> None:
        raise NotImplementedError
