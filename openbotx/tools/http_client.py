import json
from typing import Any

import httpx

from openbotx.tools.base import Tool


class HttpClientTool(Tool):
    """Full HTTP client for making API requests."""

    name = "http_client"
    description = (
        "Make HTTP requests with full control over method, headers, body, "
        "and content type. Supports GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS."
    )
    parameters = {
        "type": "object",
        "properties": {
            "method": {
                "type": "string",
                "enum": ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
                "description": "HTTP method",
            },
            "url": {"type": "string", "description": "Request URL"},
            "headers": {
                "type": "object",
                "description": "Request headers as key-value pairs",
            },
            "body": {"type": "string", "description": "Request body"},
            "content_type": {
                "type": "string",
                "enum": ["json", "form", "text", "xml"],
                "description": "Body content type (default: json)",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (default: 30)",
            },
            "follow_redirects": {
                "type": "boolean",
                "description": "Follow redirects (default: true)",
            },
        },
        "required": ["method", "url"],
    }

    async def execute(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        body: str | None = None,
        content_type: str = "json",
        timeout: int = 30,
        follow_redirects: bool = True,
        **kwargs: Any,
    ) -> str:
        try:
            request_headers = dict(headers) if headers else {}

            content_type_map = {
                "json": "application/json",
                "form": "application/x-www-form-urlencoded",
                "text": "text/plain",
                "xml": "application/xml",
            }

            if body and "Content-Type" not in request_headers:
                ct = content_type_map.get(content_type, "application/json")
                request_headers["Content-Type"] = ct

            async with httpx.AsyncClient(
                follow_redirects=follow_redirects, timeout=timeout
            ) as client:
                response = await client.request(
                    method=method.upper(),
                    url=url,
                    headers=request_headers,
                    content=body.encode("utf-8") if body else None,
                )

            response_body = response.text
            max_body = 10000
            truncated = len(response_body) > max_body
            if truncated:
                response_body = response_body[:max_body]

            result = {
                "status": response.status_code,
                "headers": dict(response.headers),
                "body": response_body,
                "truncated": truncated,
            }
            return json.dumps(result, ensure_ascii=False)

        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)
