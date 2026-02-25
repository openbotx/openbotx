from __future__ import annotations

import asyncio
import base64
import mimetypes
from pathlib import Path

from openbotx.storage.base import DirEntry, StorageProvider


class S3Storage(StorageProvider):
    """AWS S3 storage provider."""

    def __init__(
        self,
        bucket: str,
        region: str = "us-east-1",
        access_key: str = "",
        secret_key: str = "",
    ):
        import boto3

        self.bucket = bucket
        self._region = region
        self._client = boto3.client(
            "s3",
            region_name=region,
            aws_access_key_id=access_key or None,
            aws_secret_access_key=secret_key or None,
        )

    async def read(self, path: str) -> bytes:
        response = await asyncio.to_thread(self._client.get_object, Bucket=self.bucket, Key=path)
        return await asyncio.to_thread(response["Body"].read)

    async def write(self, path: str, data: bytes) -> None:
        await asyncio.to_thread(self._client.put_object, Bucket=self.bucket, Key=path, Body=data)

    async def delete(self, path: str) -> None:
        await asyncio.to_thread(self._client.delete_object, Bucket=self.bucket, Key=path)

    async def list(self, prefix: str = "") -> list[str]:
        response = await asyncio.to_thread(
            self._client.list_objects_v2, Bucket=self.bucket, Prefix=prefix
        )
        return [obj["Key"] for obj in response.get("Contents", [])]

    async def exists(self, path: str) -> bool:
        try:
            await asyncio.to_thread(self._client.head_object, Bucket=self.bucket, Key=path)
            return True
        except Exception:
            return False

    async def list_dir(self, path: str = "") -> list[DirEntry]:
        prefix = f"{path}/" if path and not path.endswith("/") else path
        entries: list[DirEntry] = []
        continuation_token = None

        while True:
            kwargs: dict = {"Bucket": self.bucket, "Prefix": prefix, "Delimiter": "/"}
            if continuation_token:
                kwargs["ContinuationToken"] = continuation_token

            response = await asyncio.to_thread(self._client.list_objects_v2, **kwargs)

            for cp in response.get("CommonPrefixes", []):
                dir_path = cp["Prefix"].rstrip("/")
                name = dir_path.rsplit("/", 1)[-1]
                entries.append(DirEntry(name=name, path=dir_path, is_dir=True))

            for obj in response.get("Contents", []):
                key = obj["Key"]
                if key == prefix:
                    continue
                name = key.rsplit("/", 1)[-1]
                if not name:
                    continue
                entries.append(DirEntry(name=name, path=key, is_dir=False, size=obj.get("Size", 0)))

            if response.get("IsTruncated"):
                continuation_token = response.get("NextContinuationToken")
            else:
                break

        entries.sort(key=lambda e: e.name)
        return entries

    async def create_dir(self, path: str) -> None:
        key = f"{path}/" if not path.endswith("/") else path
        await asyncio.to_thread(self._client.put_object, Bucket=self.bucket, Key=key, Body=b"")

    async def delete_dir(self, path: str) -> None:
        prefix = f"{path}/" if not path.endswith("/") else path
        continuation_token = None

        while True:
            kwargs: dict = {"Bucket": self.bucket, "Prefix": prefix}
            if continuation_token:
                kwargs["ContinuationToken"] = continuation_token

            response = await asyncio.to_thread(self._client.list_objects_v2, **kwargs)
            objects = [{"Key": obj["Key"]} for obj in response.get("Contents", [])]

            if objects:
                await asyncio.to_thread(
                    self._client.delete_objects,
                    Bucket=self.bucket,
                    Delete={"Objects": objects},
                )

            if response.get("IsTruncated"):
                continuation_token = response.get("NextContinuationToken")
            else:
                break

    async def size(self, path: str) -> int:
        response = await asyncio.to_thread(self._client.head_object, Bucket=self.bucket, Key=path)
        return response.get("ContentLength", 0)

    async def is_directory(self, path: str) -> bool:
        prefix = f"{path}/" if not path.endswith("/") else path
        response = await asyncio.to_thread(
            self._client.list_objects_v2, Bucket=self.bucket, Prefix=prefix, MaxKeys=1
        )
        return response.get("KeyCount", 0) > 0

    def get_url(self, path: str) -> str:
        return f"https://{self.bucket}.s3.{self._region}.amazonaws.com/{path}"

    def get_data_uri(self, path: str) -> str:
        response = self._client.get_object(Bucket=self.bucket, Key=path)
        data = response["Body"].read()
        mime, _ = mimetypes.guess_type(Path(path).name)
        if not mime:
            mime = "application/octet-stream"
        encoded = base64.b64encode(data).decode("ascii")
        return f"data:{mime};base64,{encoded}"
