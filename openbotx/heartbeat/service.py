"""Heartbeat service — periodic agent wake-up to check for tasks."""

import asyncio
import logging
from pathlib import Path

from openbotx.bus.events import InboundMessage
from openbotx.bus.queue import MessageBus

logger = logging.getLogger(__name__)

HEARTBEAT_PROMPT = """Read HEARTBEAT.md in your workspace (if it exists).
Follow any instructions or tasks listed there.
If nothing needs attention, reply with just: HEARTBEAT_OK"""


class HeartbeatService:
    """Periodic heartbeat that wakes the agent to check HEARTBEAT.md for tasks."""

    def __init__(
        self,
        workspace: Path,
        bus: MessageBus,
        interval: int = 1800,
        enabled: bool = True,
    ):
        self._workspace = workspace
        self._bus = bus
        self._interval = interval
        self._enabled = enabled
        self._running = False
        self._task: asyncio.Task | None = None

    @property
    def heartbeat_file(self) -> Path:
        return self._workspace / "HEARTBEAT.md"

    async def start(self) -> None:
        if not self._enabled:
            logger.info("heartbeat disabled")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("heartbeat started (every %ds)", self._interval)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self._interval)
                if self._running:
                    await self._tick()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("heartbeat error: %s", e)

    async def _tick(self) -> None:
        content = self._read_heartbeat_file()
        if self._is_heartbeat_empty(content):
            logger.debug("heartbeat: no tasks")
            return

        logger.info("heartbeat: sending tasks to agent")
        msg = InboundMessage(
            channel="heartbeat",
            sender_id="heartbeat",
            chat_id="heartbeat",
            content=HEARTBEAT_PROMPT,
        )
        await self._bus.publish_inbound(msg)

    @staticmethod
    def _is_heartbeat_empty(content: str | None) -> bool:
        """Check if HEARTBEAT.md has no actionable content."""
        if not content:
            return True

        for line in content.split("\n"):
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("<!--"):
                continue
            return False

        return True

    def _read_heartbeat_file(self) -> str | None:
        if self.heartbeat_file.exists():
            try:
                return self.heartbeat_file.read_text()
            except Exception:
                return None
        return None
