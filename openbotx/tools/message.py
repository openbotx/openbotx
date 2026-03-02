from collections.abc import Awaitable, Callable
from typing import Any

from openbotx.bus.events import OutboundMessage
from openbotx.tools.base import Tool
from openbotx.tools.context import RequestContext


class MessageTool(Tool):
    """Tool to send messages to users."""

    name = "message"
    description = "Send a message to the user."
    parameters = {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The message content to send",
            },
            "channel": {
                "type": "string",
                "description": "Optional: target channel",
            },
            "chat_id": {
                "type": "string",
                "description": "Optional: target chat/user ID",
            },
            "media": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional: file paths to attach",
            },
        },
        "required": ["content"],
    }

    def __init__(
        self,
        send_callback: Callable[[OutboundMessage], Awaitable[None]] | None = None,
    ):
        self._send_callback = send_callback

    def set_send_callback(self, callback: Callable[[OutboundMessage], Awaitable[None]]) -> None:
        self._send_callback = callback

    async def execute(
        self,
        content: str,
        channel: str | None = None,
        chat_id: str | None = None,
        media: list[str] | None = None,
        **kwargs: Any,
    ) -> str:
        ctx: RequestContext | None = kwargs.get("_context")
        channel = channel or (ctx.channel if ctx else "")
        chat_id = chat_id or (ctx.chat_id if ctx else "")

        if not channel or not chat_id:
            return "Error: No target channel/chat specified"
        if not self._send_callback:
            return "Error: Message sending not configured"

        msg = OutboundMessage(
            channel=channel,
            chat_id=chat_id,
            content=content,
            media=media or [],
            metadata={"message_id": ctx.message_id if ctx else None},
        )

        try:
            await self._send_callback(msg)
            return f"Message sent to {channel}:{chat_id}"
        except Exception as e:
            return f"Error sending message: {e}"
