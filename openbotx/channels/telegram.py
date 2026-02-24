from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable

from telegram import ReplyParameters, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest

from openbotx.bus.events import InboundMessage, OutboundMessage
from openbotx.channels.base import BaseChannel
from openbotx.storage.base import StorageProvider

logger = logging.getLogger(__name__)


class TelegramChannel(BaseChannel):
    def __init__(
        self,
        token: str,
        storage: StorageProvider,
        on_message: Callable[[InboundMessage], Awaitable[None]] | None = None,
        allow_from: list[str] | None = None,
        proxy: str | None = None,
        reply_to_message: bool = False,
    ):
        super().__init__(name="telegram", on_message=on_message, allow_from=allow_from)
        self._token = token
        self._storage = storage
        self._proxy = proxy
        self._reply_to_message = reply_to_message
        self._app: Application | None = None
        self._typing_tasks: dict[str, asyncio.Task] = {}

    async def start(self) -> None:
        if not self._token:
            logger.error("telegram bot token not configured")
            return

        self._running = True

        req = HTTPXRequest(
            connection_pool_size=16,
            pool_timeout=5.0,
            connect_timeout=30.0,
            read_timeout=30.0,
        )
        builder = Application.builder().token(self._token).request(req).get_updates_request(req)
        if self._proxy:
            builder = builder.proxy(self._proxy).get_updates_proxy(self._proxy)

        self._app = builder.build()
        self._app.add_error_handler(self._on_error)

        self._app.add_handler(CommandHandler("start", self._on_start))
        self._app.add_handler(CommandHandler("new", self._on_command))
        self._app.add_handler(CommandHandler("help", self._on_help))
        self._app.add_handler(
            MessageHandler(
                (
                    filters.TEXT
                    | filters.PHOTO
                    | filters.VOICE
                    | filters.AUDIO
                    | filters.Document.ALL
                )
                & ~filters.COMMAND,
                self._on_message_received,
            )
        )

        logger.info("starting telegram bot (polling mode)")

        await self._app.initialize()
        await self._app.start()

        bot_info = await self._app.bot.get_me()
        logger.info("telegram bot @%s connected", bot_info.username)

        await self._app.updater.start_polling(
            allowed_updates=["message"],
            drop_pending_updates=True,
        )

        while self._running:
            await asyncio.sleep(1)

    async def stop(self) -> None:
        self._running = False

        for chat_id in list(self._typing_tasks):
            self._stop_typing(chat_id)

        if self._app:
            logger.info("stopping telegram bot")
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()
            self._app = None

    async def send(self, msg: OutboundMessage) -> None:
        if not self._app:
            logger.warning("telegram bot not running, cannot send")
            return

        self._stop_typing(msg.chat_id)

        try:
            chat_id = int(msg.chat_id)
        except ValueError:
            logger.error("invalid telegram chat_id: %s", msg.chat_id)
            return

        reply_params = None
        if self._reply_to_message:
            reply_to_message_id = msg.metadata.get("message_id")
            if reply_to_message_id:
                reply_params = ReplyParameters(
                    message_id=reply_to_message_id,
                    allow_sending_without_reply=True,
                )

        for media_path in msg.media or []:
            try:
                data = await self._storage.read(media_path)
                media_type = self._guess_media_type(media_path)
                sender = {
                    "photo": self._app.bot.send_photo,
                    "voice": self._app.bot.send_voice,
                    "audio": self._app.bot.send_audio,
                }.get(media_type, self._app.bot.send_document)
                param = (
                    "photo"
                    if media_type == "photo"
                    else media_type
                    if media_type in ("voice", "audio")
                    else "document"
                )
                await sender(
                    chat_id=chat_id,
                    **{param: data},
                    reply_parameters=reply_params,
                )
            except Exception as e:
                filename = media_path.rsplit("/", 1)[-1]
                logger.error("failed to send media %s: %s", media_path, e)
                await self._app.bot.send_message(
                    chat_id=chat_id,
                    text=f"[failed to send: {filename}]",
                    reply_parameters=reply_params,
                )

        if msg.content and msg.content != "[empty message]":
            for chunk in self._split_message(msg.content):
                try:
                    html = self._markdown_to_telegram_html(chunk)
                    await self._app.bot.send_message(
                        chat_id=chat_id,
                        text=html,
                        parse_mode="HTML",
                        reply_parameters=reply_params,
                    )
                except Exception:
                    try:
                        await self._app.bot.send_message(
                            chat_id=chat_id,
                            text=chunk,
                            reply_parameters=reply_params,
                        )
                    except Exception as e:
                        logger.error("error sending telegram message: %s", e)

    # -- handlers --

    async def _on_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user:
            return
        user = update.effective_user
        await update.message.reply_text(
            f"Hi {user.first_name}! Send me a message and I'll respond.\n"
            "Type /help to see available commands."
        )

    async def _on_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        await update.message.reply_text(
            "Available commands:\n/new - Start a new conversation\n/help - Show this help"
        )

    async def _on_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user:
            return
        sender_id = self._build_sender_id(update.effective_user)
        chat_id = str(update.message.chat_id)

        if not self.is_allowed(sender_id):
            logger.warning("blocked command from unauthorized user %s", sender_id)
            return

        self._start_typing(chat_id)
        await self._dispatch_inbound(
            sender_id=sender_id,
            chat_id=chat_id,
            content=update.message.text or "",
            metadata={"message_id": update.message.message_id},
        )

    async def _on_message_received(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not update.message or not update.effective_user:
            return

        message = update.message
        user = update.effective_user
        sender_id = self._build_sender_id(user)
        chat_id = str(message.chat_id)

        if not self.is_allowed(sender_id):
            logger.warning("blocked message from unauthorized user %s", sender_id)
            return

        content_parts: list[str] = []
        media_paths: list[str] = []

        if message.text:
            content_parts.append(message.text)
        if message.caption:
            content_parts.append(message.caption)

        media_file = None
        media_type = None

        if message.photo:
            media_file = message.photo[-1]
            media_type = "image"
        elif message.voice:
            media_file = message.voice
            media_type = "voice"
        elif message.audio:
            media_file = message.audio
            media_type = "audio"
        elif message.document:
            media_file = message.document
            media_type = "file"

        if media_file and self._app:
            try:
                tg_file = await self._app.bot.get_file(media_file.file_id)
                ext = self._get_extension(media_type, getattr(media_file, "mime_type", None))
                filename = f"{media_file.file_id[:16]}{ext}"
                storage_path = f"public/media/{filename}"

                data = await tg_file.download_as_bytearray()
                await self._storage.write(storage_path, bytes(data))

                media_paths.append(storage_path)
                content_parts.append(f"[{media_type}: {filename}]")
                logger.debug("downloaded %s to %s", media_type, storage_path)
            except Exception as e:
                logger.error("failed to download media: %s", e)
                content_parts.append(f"[{media_type}: download failed]")

        content = "\n".join(content_parts) if content_parts else "[empty message]"

        logger.debug("telegram message from %s: %s", sender_id, content[:80])

        self._start_typing(chat_id)

        await self._dispatch_inbound(
            sender_id=sender_id,
            chat_id=chat_id,
            content=content,
            media=media_paths,
            metadata={
                "message_id": message.message_id,
                "user_id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "is_group": message.chat.type != "private",
            },
        )

    # -- typing indicator --

    def _start_typing(self, chat_id: str) -> None:
        self._stop_typing(chat_id)
        self._typing_tasks[chat_id] = asyncio.create_task(self._typing_loop(chat_id))

    def _stop_typing(self, chat_id: str) -> None:
        task = self._typing_tasks.pop(chat_id, None)
        if task and not task.done():
            task.cancel()

    async def _typing_loop(self, chat_id: str) -> None:
        try:
            while self._app:
                await self._app.bot.send_chat_action(chat_id=int(chat_id), action="typing")
                await asyncio.sleep(4)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug("typing indicator stopped for %s: %s", chat_id, e)

    # -- internal helpers --

    async def _dispatch_inbound(
        self,
        sender_id: str,
        chat_id: str,
        content: str,
        media: list[str] | None = None,
        metadata: dict | None = None,
    ) -> None:
        if not self._on_message:
            logger.warning("no message handler configured for telegram channel")
            return

        msg = InboundMessage(
            channel="telegram",
            sender_id=sender_id,
            chat_id=chat_id,
            content=content,
            media=media or [],
            metadata=metadata or {},
        )
        await self._on_message(msg)

    @staticmethod
    def _build_sender_id(user) -> str:
        sid = str(user.id)
        return f"{sid}|{user.username}" if user.username else sid

    @staticmethod
    def _guess_media_type(path: str) -> str:
        ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
        if ext in ("jpg", "jpeg", "png", "gif", "webp"):
            return "photo"
        if ext == "ogg":
            return "voice"
        if ext in ("mp3", "m4a", "wav", "aac"):
            return "audio"
        return "document"

    @staticmethod
    def _get_extension(media_type: str | None, mime_type: str | None) -> str:
        if mime_type:
            ext_map = {
                "image/jpeg": ".jpg",
                "image/png": ".png",
                "image/gif": ".gif",
                "audio/ogg": ".ogg",
                "audio/mpeg": ".mp3",
                "audio/mp4": ".m4a",
            }
            if mime_type in ext_map:
                return ext_map[mime_type]
        type_map = {"image": ".jpg", "voice": ".ogg", "audio": ".mp3", "file": ""}
        return type_map.get(media_type or "", "")

    @staticmethod
    def _markdown_to_telegram_html(text: str) -> str:
        if not text:
            return ""

        code_blocks: list[str] = []

        def _save_code_block(m: re.Match) -> str:
            code_blocks.append(m.group(1))
            return f"\x00CB{len(code_blocks) - 1}\x00"

        text = re.sub(r"```[\w]*\n?([\s\S]*?)```", _save_code_block, text)

        inline_codes: list[str] = []

        def _save_inline_code(m: re.Match) -> str:
            inline_codes.append(m.group(1))
            return f"\x00IC{len(inline_codes) - 1}\x00"

        text = re.sub(r"`([^`]+)`", _save_inline_code, text)

        text = re.sub(r"^#{1,6}\s+(.+)$", r"\1", text, flags=re.MULTILINE)
        text = re.sub(r"^>\s*(.*)$", r"\1", text, flags=re.MULTILINE)
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)
        text = re.sub(r"(?<![a-zA-Z0-9])_([^_]+)_(?![a-zA-Z0-9])", r"<i>\1</i>", text)
        text = re.sub(r"~~(.+?)~~", r"<s>\1</s>", text)
        text = re.sub(r"^[-*]\s+", "\u2022 ", text, flags=re.MULTILINE)

        for i, code in enumerate(inline_codes):
            escaped = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            text = text.replace(f"\x00IC{i}\x00", f"<code>{escaped}</code>")

        for i, code in enumerate(code_blocks):
            escaped = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            text = text.replace(f"\x00CB{i}\x00", f"<pre><code>{escaped}</code></pre>")

        return text

    @staticmethod
    def _split_message(content: str, max_len: int = 4000) -> list[str]:
        if len(content) <= max_len:
            return [content]
        chunks: list[str] = []
        while content:
            if len(content) <= max_len:
                chunks.append(content)
                break
            cut = content[:max_len]
            pos = cut.rfind("\n")
            if pos == -1:
                pos = cut.rfind(" ")
            if pos == -1:
                pos = max_len
            chunks.append(content[:pos])
            content = content[pos:].lstrip()
        return chunks

    async def _on_error(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        logger.error("telegram error: %s", context.error)
