import base64
import mimetypes
from pathlib import Path

from openbotx.storage.base import StorageProvider


class LocalStorage(StorageProvider):
    """Local filesystem storage provider.

    base_path is the project root directory.
    Paths are relative to it (e.g. "public/media/photo.png", "workspace/data.csv").
    """

    def __init__(self, base_path: Path, public_url: str = ""):
        self.base_path = base_path
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._public_url = public_url.rstrip("/")

    def _resolve(self, path: str) -> Path:
        resolved = (self.base_path / path).resolve()
        resolved.relative_to(self.base_path.resolve())
        return resolved

    async def read(self, path: str) -> bytes:
        return self._resolve(path).read_bytes()

    async def write(self, path: str, data: bytes) -> None:
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    async def delete(self, path: str) -> None:
        target = self._resolve(path)
        if target.exists():
            target.unlink()

    async def list(self, prefix: str = "") -> list[str]:
        base = self._resolve(prefix) if prefix else self.base_path
        if not base.is_dir():
            return []
        return [str(p.relative_to(self.base_path)) for p in base.rglob("*") if p.is_file()]

    async def exists(self, path: str) -> bool:
        return self._resolve(path).exists()

    def get_url(self, path: str) -> str:
        return f"{self._public_url}/{path}"

    def get_data_uri(self, path: str) -> str:
        file_path = self._resolve(path)
        data = file_path.read_bytes()
        mime, _ = mimetypes.guess_type(file_path.name)
        if not mime:
            mime = "application/octet-stream"
        encoded = base64.b64encode(data).decode("ascii")
        return f"data:{mime};base64,{encoded}"
