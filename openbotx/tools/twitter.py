import base64
import hashlib
import hmac
import json
import logging
import time
import uuid
from typing import Any
from urllib.parse import quote

import httpx

from openbotx.config.schema import TwitterConfig
from openbotx.storage.base import StorageProvider, detect_mime
from openbotx.tools.base import Tool

logger = logging.getLogger(__name__)

_API_URL = "https://api.twitter.com/2/tweets"
_UPLOAD_URL = "https://upload.twitter.com/1.1/media/upload.json"


def _pct_encode(value: str) -> str:
    return quote(str(value), safe="")


def _build_oauth_header(
    method: str,
    url: str,
    api_key: str,
    api_secret: str,
    access_token: str,
    access_token_secret: str,
) -> str:
    oauth = {
        "oauth_consumer_key": api_key,
        "oauth_nonce": uuid.uuid4().hex,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": access_token,
        "oauth_version": "1.0",
    }

    # signature base string (RFC 5849)
    sorted_params = "&".join(f"{_pct_encode(k)}={_pct_encode(v)}" for k, v in sorted(oauth.items()))
    base_string = f"{method.upper()}&{_pct_encode(url)}&{_pct_encode(sorted_params)}"
    signing_key = f"{_pct_encode(api_secret)}&{_pct_encode(access_token_secret)}"

    signature = base64.b64encode(
        hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1).digest()
    ).decode()
    oauth["oauth_signature"] = signature

    parts = [f'{_pct_encode(k)}="{_pct_encode(v)}"' for k, v in sorted(oauth.items())]
    return "OAuth " + ", ".join(parts)


class TwitterTool(Tool):
    name = "twitter_post"
    description = (
        "Post a tweet on Twitter/X. Supports text-only tweets, "
        "tweets with images from storage, and threads via reply_to_id."
    )
    parameters = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Tweet text (max 280 characters)",
            },
            "media_path": {
                "type": "string",
                "description": "Storage path to image to attach (e.g. public/media/image.png)",
            },
            "reply_to_id": {
                "type": "string",
                "description": "Tweet ID to reply to for creating threads",
            },
        },
        "required": ["text"],
    }

    def __init__(self, config: TwitterConfig, storage: StorageProvider):
        self._config = config
        self._storage = storage

    def _auth(self, method: str, url: str) -> str:
        return _build_oauth_header(
            method,
            url,
            self._config.consumer_key,
            self._config.consumer_secret,
            self._config.access_token,
            self._config.access_token_secret,
        )

    async def _upload_media(self, path: str) -> str:
        data = await self._storage.read(path)
        mime = detect_mime(data)
        filename = path.rsplit("/", 1)[-1]

        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(
                _UPLOAD_URL,
                headers={"Authorization": self._auth("POST", _UPLOAD_URL)},
                files={"media": (filename, data, mime)},
            )

        if r.status_code not in (200, 201, 202):
            raise RuntimeError(f"Media upload failed ({r.status_code}): {r.text}")

        media_id = r.json().get("media_id_string")
        if not media_id:
            raise RuntimeError("No media_id in upload response")
        return media_id

    async def _create_tweet(
        self,
        text: str,
        media_ids: list[str] | None = None,
        reply_to_id: str | None = None,
    ) -> dict:
        payload: dict[str, Any] = {"text": text}
        if media_ids:
            payload["media"] = {"media_ids": media_ids}
        if reply_to_id:
            payload["reply"] = {"in_reply_to_tweet_id": reply_to_id}

        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                _API_URL,
                headers={
                    "Authorization": self._auth("POST", _API_URL),
                    "Content-Type": "application/json",
                },
                json=payload,
            )

        return {"status": r.status_code, "body": r.json()}

    async def execute(
        self,
        text: str,
        media_path: str | None = None,
        reply_to_id: str | None = None,
        **kwargs: Any,
    ) -> str:
        try:
            media_ids = None
            if media_path:
                media_id = await self._upload_media(media_path)
                media_ids = [media_id]

            result = await self._create_tweet(text, media_ids=media_ids, reply_to_id=reply_to_id)

            if result["status"] in (200, 201):
                tweet_data = result["body"].get("data", {})
                return json.dumps(
                    {
                        "success": True,
                        "tweet_id": tweet_data.get("id", ""),
                        "text": text,
                    },
                    ensure_ascii=False,
                )

            return json.dumps(
                {
                    "error": f"Twitter API error ({result['status']})",
                    "details": result["body"],
                },
                ensure_ascii=False,
            )
        except Exception as e:
            logger.error("twitter post failed: %s", e)
            return json.dumps({"error": str(e)}, ensure_ascii=False)
