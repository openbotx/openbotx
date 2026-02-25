import asyncio
import logging
from typing import Any

from openbotx.bus.events import OutboundMessage
from openbotx.bus.queue import MessageBus
from openbotx.channels.base import BaseChannel
from openbotx.config.schema import ChannelsConfig
from openbotx.storage.base import StorageProvider

logger = logging.getLogger(__name__)


class ChannelManager:
    """Manages chat channels lifecycle and message routing."""

    def __init__(
        self,
        config: ChannelsConfig,
        bus: MessageBus,
        storage: StorageProvider,
        ws_manager=None,
    ):
        self.config = config
        self.bus = bus
        self._storage = storage
        self._ws_manager = ws_manager
        self._channels: dict[str, BaseChannel] = {}
        self._outbound_task: asyncio.Task | None = None
        self._send_progress = config.send_progress
        self._send_tool_hints = config.send_tool_hints

    def _init_channels(self) -> None:
        if self.config.telegram.enabled and self.config.telegram.token:
            try:
                from openbotx.channels.telegram import TelegramChannel

                channel = TelegramChannel(
                    token=self.config.telegram.token,
                    storage=self._storage,
                    on_message=self.bus.publish_inbound,
                    allow_from=self.config.telegram.allowed_users,
                    proxy=self.config.telegram.proxy,
                    reply_to_message=self.config.telegram.reply_to_message,
                )
                self._channels["telegram"] = channel
            except Exception as e:
                logger.error("Failed to init Telegram channel: %s", e)

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
                await channel.stop()
                logger.info("Channel stopped: %s", name)
            except Exception as e:
                logger.error("Failed to stop channel %s: %s", name, e)

    async def start_channel(self, name: str) -> bool:
        channel = self._channels.get(name)
        if not channel:
            if name == "telegram" and self.config.telegram.token:
                from openbotx.channels.telegram import TelegramChannel

                channel = TelegramChannel(
                    token=self.config.telegram.token,
                    storage=self._storage,
                    on_message=self.bus.publish_inbound,
                    allow_from=self.config.telegram.allowed_users,
                    proxy=self.config.telegram.proxy,
                    reply_to_message=self.config.telegram.reply_to_message,
                )
                self._channels[name] = channel

        if channel and not channel.is_running:
            await channel.start()
            self._broadcast_channel_status(name, channel.is_running)
            return True
        return False

    async def stop_channel(self, name: str) -> bool:
        channel = self._channels.get(name)
        if channel and channel.is_running:
            await channel.stop()
            self._broadcast_channel_status(name, channel.is_running)
            return True
        return False

    def _broadcast_channel_status(self, name: str, running: bool) -> None:
        if self._ws_manager:
            asyncio.create_task(
                self._ws_manager.broadcast(
                    "channel:status", {"name": name, "running": running}
                )
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

        if is_progress and not self._send_progress:
            return
        if is_tool_hint and not self._send_tool_hints:
            return

        if msg.channel == "web":
            if self._ws_manager:
                await self._ws_manager.broadcast(
                    "chat:message",
                    {
                        "content": msg.content,
                        "chat_id": msg.chat_id,
                        "task_id": msg.metadata.get("task_id"),
                    },
                )
            return

        channel = self._channels.get(msg.channel)
        if channel and channel.is_running:
            try:
                await channel.send(msg)
            except Exception as e:
                logger.error("Failed to send to %s: %s", msg.channel, e)
