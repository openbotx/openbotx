from abc import ABC, abstractmethod


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

    @abstractmethod
    def get_url(self, path: str) -> str:
        """Return the public URL for the given path."""
        pass

    @abstractmethod
    def get_data_uri(self, path: str) -> str:
        """Read file and return as data URI (data:mime;base64,...)."""
        pass
