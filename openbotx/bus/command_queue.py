import asyncio
import logging
from collections import deque
from collections.abc import Coroutine
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class _LaneState:
    """Internal state for a single lane."""

    queue: deque[tuple[asyncio.Future, Coroutine]] = field(default_factory=deque)
    active: int = 0
    max_concurrent: int = 1


class CommandQueue:
    """Lane-based async command queue for concurrent message processing.

    Each lane (identified by a string key) has its own FIFO queue with
    configurable concurrency. A global semaphore caps the total number
    of parallel tasks across all lanes.

    Typical lane keys:
        - session_key (channel:chat_id) — serializes within a chat,
          parallel across different chats
        - "cron" — separate lane for scheduled jobs
        - "subagent" — separate lane for spawned subagents
    """

    def __init__(self, max_total: int = 1):
        self._lanes: dict[str, _LaneState] = {}
        self._semaphore = asyncio.Semaphore(max_total)
        self._tasks: set[asyncio.Task] = set()

    def set_lane_concurrency(self, lane: str, max_concurrent: int) -> None:
        """Configure max concurrency for a specific lane."""
        state = self._get_lane(lane)
        state.max_concurrent = max(1, max_concurrent)

    async def enqueue(self, lane: str, coro: Coroutine) -> Any:
        """Enqueue a coroutine in the given lane and wait for its result."""
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        state = self._get_lane(lane)
        state.queue.append((future, coro))
        self._pump(lane)
        return await future

    def enqueue_nowait(self, lane: str, coro: Coroutine) -> None:
        """Enqueue a coroutine without waiting for the result."""
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        future.add_done_callback(lambda f: f.exception() if not f.cancelled() else None)
        state = self._get_lane(lane)
        state.queue.append((future, coro))
        self._pump(lane)

    async def drain(self) -> None:
        """Wait for all active tasks to complete."""
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

    @property
    def active_count(self) -> int:
        return sum(s.active for s in self._lanes.values())

    def _get_lane(self, lane: str) -> _LaneState:
        if lane not in self._lanes:
            self._lanes[lane] = _LaneState()
        return self._lanes[lane]

    def _pump(self, lane: str) -> None:
        """Drain queued tasks up to the lane's concurrency limit."""
        state = self._get_lane(lane)
        while state.queue and state.active < state.max_concurrent:
            future, coro = state.queue.popleft()
            state.active += 1
            task = asyncio.create_task(self._run(lane, future, coro))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

    async def _run(self, lane: str, future: asyncio.Future, coro: Coroutine) -> None:
        """Execute a coroutine under the global semaphore."""
        state = self._get_lane(lane)
        async with self._semaphore:
            try:
                result = await coro
                if not future.done():
                    future.set_result(result)
            except Exception as e:
                if not future.done():
                    future.set_exception(e)
                logger.error("command queue task failed in lane %s: %s", lane, e, exc_info=True)
            finally:
                state.active -= 1
                self._pump(lane)
