import asyncio
import logging
from typing import Any

from openbotx.bus.dispatcher import EventDispatcher
from openbotx.bus.events import OutboundMessage
from openbotx.bus.queue import MessageBus
from openbotx.channels.base import BaseChannel
from openbotx.config.schema import ChannelsConfig, CredentialConfig
from openbotx.storage.base import StorageProvider

logger = logging.getLogger(__name__)


class ChannelManager:
    """Manages chat channels lifecycle and message routing."""

    def __init__(
        self,
        config: ChannelsConfig,
        bus: MessageBus,
        storage: StorageProvider,
        dispatcher: EventDispatcher,
        credentials: dict[str, CredentialConfig] | None = None,
    ):
        self.config = config
        self.bus = bus
        self._storage = storage
        self._dispatcher = dispatcher
        self._credentials = credentials or {}
        self._channels: dict[str, BaseChannel] = {}
        self._outbound_task: asyncio.Task | None = None
        self._send_progress = config.send_progress
        self._send_tool_hints = config.send_tool_hints

    def _create_channel(self, name: str) -> BaseChannel | None:
        """Create a channel instance from current config."""
        if name == "telegram" and self.config.telegram.credential:
            cred = self._credentials.get(self.config.telegram.credential)
            if not cred:
                logger.error(
                    "credential '%s' not found for telegram",
                    self.config.telegram.credential,
                )
                return None
            try:
                from openbotx.channels.telegram import TelegramChannel

                return TelegramChannel(
                    token=cred.key,
                    storage=self._storage,
                    on_message=self.bus.publish_inbound,
                    allow_from=self.config.telegram.allowed_users,
                    proxy=self.config.telegram.proxy,
                    reply_to_message=self.config.telegram.reply_to_message,
                )
            except Exception as e:
                logger.error("Failed to create %s channel: %s", name, e)
        return None

    def _init_channels(self) -> None:
        if self.config.telegram.enabled and self.config.telegram.credential:
            channel = self._create_channel("telegram")
            if channel:
                self._channels["telegram"] = channel

    async def start(self) -> None:
        self._init_channels()
        for name, channel in self._channels.items():
            try:
                await channel.start()
                logger.info("Channel started: %s", name)
            except Exception as e:
                logger.error("Failed to start channel %s: %s", name, e)

        self._outbound_task = asyncio.create_task(self._dispatch_outbound())

    async def stop(self) -> None:
        if self._outbound_task:
            self._outbound_task.cancel()
            try:
                await self._outbound_task
            except asyncio.CancelledError:
                pass

        for name, channel in self._channels.items():
            try:
                await asyncio.wait_for(channel.stop(), timeout=10)
                logger.info("Channel stopped: %s", name)
            except TimeoutError:
                logger.warning("Channel %s stop timed out, forcing", name)
            except Exception as e:
                logger.error("Failed to stop channel %s: %s", name, e)

    async def start_channel(self, name: str) -> bool:
        existing = self._channels.get(name)
        if existing and existing.is_running:
            await existing.stop()

        channel = self._create_channel(name)
        if not channel:
            self._channels.pop(name, None)
            self._broadcast_channel_status(name, False)
            return False

        self._channels[name] = channel
        await channel.start()
        self._broadcast_channel_status(name, channel.is_running)
        return True

    async def stop_channel(self, name: str) -> bool:
        channel = self._channels.get(name)
        if channel and channel.is_running:
            await channel.stop()
            self._broadcast_channel_status(name, channel.is_running)
            return True
        return False

    def _broadcast_channel_status(self, name: str, running: bool) -> None:
        asyncio.create_task(
            self._dispatcher.broadcast("channel:status", {"name": name, "running": running})
        )

    def get_status(self) -> dict[str, Any]:
        status = {
            "web": {"running": True, "type": "builtin"},
        }

        for name, channel in self._channels.items():
            status[name] = {
                "running": channel.is_running,
                "type": name,
            }

        # show telegram even if not initialized
        if "telegram" not in status:
            status["telegram"] = {
                "running": False,
                "type": "telegram",
                "enabled": self.config.telegram.enabled,
            }

        return status

    async def _dispatch_outbound(self) -> None:
        while True:
            try:
                msg = await self.bus.consume_outbound()
                await self._route_message(msg)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Outbound dispatch error: %s", e)

    async def _route_message(self, msg: OutboundMessage) -> None:
        is_progress = msg.metadata.get("progress", False)
        is_tool_hint = msg.metadata.get("tool_hint", False)
        is_forwarded_input = msg.metadata.get("forwarded_input", False)

        if is_progress and not self._send_progress:
            return
        if is_tool_hint and not self._send_tool_hints:
            return

        # send to the registered channel handler (e.g. Telegram)
        channel = self._channels.get(msg.channel)
        if channel and channel.is_running:
            try:
                await channel.send(msg)
            except Exception as e:
                logger.error("Failed to send to %s: %s", msg.channel, e)

        # forwarded input messages only go to the channel handler,
        # the web UI already has the user's message locally
        if is_forwarded_input:
            return

        # always broadcast to WebSocket so the web UI mirrors all sessions
        await self._dispatcher.broadcast(
            "chat:message",
            {
                "content": msg.content,
                "content_blocks": msg.metadata.get("content_blocks"),
                "chat_id": msg.chat_id,
                "task_id": msg.metadata.get("task_id"),
                "agent_name": msg.metadata.get("agent_name"),
            },
        )
