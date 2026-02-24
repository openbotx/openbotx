from abc import ABC, abstractmethod
from pathlib import Path


class StorageProvider(ABC):
    """Abstract base for storage providers."""

    @abstractmethod
    async def read(self, path: str) -> bytes:
        pass

    @abstractmethod
    async def write(self, path: str, data: bytes) -> None:
        pass

    @abstractmethod
    async def delete(self, path: str) -> None:
        pass

    @abstractmethod
    async def list(self, prefix: str = "") -> list[str]:
        pass

    @abstractmethod
    async def exists(self, path: str) -> bool:
        pass
