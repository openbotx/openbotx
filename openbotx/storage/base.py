from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class DirEntry:
    name: str
    path: str
    is_dir: bool
    size: int = 0


class StorageProvider(ABC):
    """Abstract base for storage providers."""

    @abstractmethod
    async def read(self, path: str) -> bytes: ...

    @abstractmethod
    async def write(self, path: str, data: bytes) -> None: ...

    @abstractmethod
    async def delete(self, path: str) -> None: ...

    @abstractmethod
    async def list(self, prefix: str = "") -> list[str]: ...

    @abstractmethod
    async def exists(self, path: str) -> bool: ...

    @abstractmethod
    async def list_dir(self, path: str = "") -> list[DirEntry]: ...

    @abstractmethod
    async def create_dir(self, path: str) -> None: ...

    @abstractmethod
    async def delete_dir(self, path: str) -> None: ...

    @abstractmethod
    async def size(self, path: str) -> int: ...

    @abstractmethod
    async def is_directory(self, path: str) -> bool: ...

    @abstractmethod
    def get_url(self, path: str) -> str:
        """Return the public URL for the given path."""

    @abstractmethod
    def get_data_uri(self, path: str) -> str:
        """Read file and return as data URI (data:mime;base64,...)."""
