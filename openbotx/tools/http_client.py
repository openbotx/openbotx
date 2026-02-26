import json
import mimetypes
from typing import Any

import httpx

from openbotx.helpers.path import PathResolver
from openbotx.tools.base import Tool


class HttpClientTool(Tool):
    """Full HTTP client with download and upload support."""

    name = "http_client"
    description = (
        "Make HTTP requests with full control over method, headers, body, "
        "and content type. Supports GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS. "
        "Use download_path to save a response as a file. "
        "Use upload_file to upload a file as multipart form data."
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
            "download_path": {
                "type": "string",
                "description": "Save response body to this file path instead of returning it",
            },
            "upload_file": {
                "type": "string",
                "description": "Path to a file to upload as multipart form data",
            },
            "upload_field": {
                "type": "string",
                "description": "Form field name for the uploaded file (default: file)",
            },
        },
        "required": ["method", "url"],
    }

    _CONTENT_TYPE_MAP = {
        "json": "application/json",
        "form": "application/x-www-form-urlencoded",
        "text": "text/plain",
        "xml": "application/xml",
    }

    _MAX_BODY_LENGTH = 50_000  # 50KB — matches WebFetchTool

    def __init__(self, resolver: PathResolver | None = None):
        self._resolver = resolver

    async def execute(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        body: str | None = None,
        content_type: str = "json",
        timeout: int = 30,
        follow_redirects: bool = True,
        download_path: str | None = None,
        upload_file: str | None = None,
        upload_field: str = "file",
        **kwargs: Any,
    ) -> str:
        try:
            if download_path:
                return await self._download(url, download_path, headers, timeout, follow_redirects)
            if upload_file:
                return await self._upload(
                    method, url, upload_file, upload_field, headers, body, timeout, follow_redirects
                )
            return await self._request(
                method, url, headers, body, content_type, timeout, follow_redirects
            )
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    async def _request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None,
        body: str | None,
        content_type: str,
        timeout: int,
        follow_redirects: bool,
    ) -> str:
        request_headers = dict(headers) if headers else {}

        if body and "Content-Type" not in request_headers:
            ct = self._CONTENT_TYPE_MAP.get(content_type, "application/json")
            request_headers["Content-Type"] = ct

        async with httpx.AsyncClient(follow_redirects=follow_redirects, timeout=timeout) as client:
            response = await client.request(
                method=method.upper(),
                url=url,
                headers=request_headers,
                content=body.encode("utf-8") if body else None,
            )

        return self._format_response(response)

    async def _download(
        self,
        url: str,
        download_path: str,
        headers: dict[str, str] | None,
        timeout: int,
        follow_redirects: bool,
    ) -> str:
        file_path = self._resolver.resolve(download_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        request_headers = dict(headers) if headers else {}

        async with httpx.AsyncClient(follow_redirects=follow_redirects, timeout=timeout) as client:
            response = await client.get(url, headers=request_headers)
            response.raise_for_status()

        file_path.write_bytes(response.content)

        result = {
            "status": response.status_code,
            "path": str(file_path),
            "size": len(response.content),
            "content_type": response.headers.get("content-type", ""),
        }
        return json.dumps(result, ensure_ascii=False)

    async def _upload(
        self,
        method: str,
        url: str,
        upload_file: str,
        upload_field: str,
        headers: dict[str, str] | None,
        body: str | None,
        timeout: int,
        follow_redirects: bool,
    ) -> str:
        file_path = self._resolver.resolve(upload_file)

        if not file_path.exists():
            return json.dumps({"error": f"File not found: {upload_file}"}, ensure_ascii=False)
        if not file_path.is_file():
            return json.dumps({"error": f"Not a file: {upload_file}"}, ensure_ascii=False)

        mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        file_data = file_path.read_bytes()

        request_headers = dict(headers) if headers else {}

        files = {upload_field: (file_path.name, file_data, mime_type)}
        data = None
        if body:
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                data = None

        async with httpx.AsyncClient(follow_redirects=follow_redirects, timeout=timeout) as client:
            response = await client.request(
                method=method.upper(),
                url=url,
                headers=request_headers,
                files=files,
                data=data,
            )

        return self._format_response(response)

    def _format_response(self, response: httpx.Response) -> str:
        response_body = response.text
        truncated = len(response_body) > self._MAX_BODY_LENGTH
        if truncated:
            response_body = response_body[: self._MAX_BODY_LENGTH]

        result = {
            "status": response.status_code,
            "headers": dict(response.headers),
            "body": response_body,
            "truncated": truncated,
        }
        return json.dumps(result, ensure_ascii=False)
