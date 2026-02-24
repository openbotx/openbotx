import asyncio
import base64
import mimetypes
from pathlib import Path

from openbotx.storage.base import StorageProvider


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
