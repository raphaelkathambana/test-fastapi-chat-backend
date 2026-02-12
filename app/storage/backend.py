"""
Storage backend abstraction layer.

Provides a protocol-based interface so the application can swap between
local filesystem and object storage (S3/MinIO) without touching business logic.
"""
from typing import Protocol, AsyncIterator
from pathlib import Path
import aiofiles
import aiofiles.os
import os
import logging

from app.config import get_settings

logger = logging.getLogger(__name__)


class StorageBackend(Protocol):
    """Protocol defining the storage interface. Implement this for new backends."""

    async def store(self, key: str, data: bytes) -> None:
        """Store file data at the given key."""
        ...

    async def retrieve(self, key: str) -> bytes:
        """Retrieve file data by key."""
        ...

    async def stream(self, key: str, chunk_size: int = 8192) -> AsyncIterator[bytes]:
        """Stream file data in chunks (for large files)."""
        ...

    async def delete(self, key: str) -> None:
        """Delete file at the given key."""
        ...

    async def exists(self, key: str) -> bool:
        """Check if a file exists at the given key."""
        ...

    async def append_chunk(self, key: str, data: bytes) -> None:
        """Append a chunk of data to an existing file (for chunked uploads)."""
        ...


class LocalStorageBackend:
    """
    Local filesystem storage backend.

    Stores files in a configurable directory with subdirectories based on
    the storage key structure. Suitable for single-server deployments
    (e.g., dealership local servers).
    """

    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"LocalStorageBackend initialized at {self.base_path.resolve()}")

    def _resolve_path(self, key: str) -> Path:
        """Resolve storage key to filesystem path, preventing path traversal."""
        # Normalize and strip leading separators to prevent escaping base_path
        clean_key = Path(key).as_posix().lstrip("/")
        resolved = (self.base_path / clean_key).resolve()

        # Security: ensure resolved path is within base_path
        if not str(resolved).startswith(str(self.base_path.resolve())):
            raise ValueError(f"Path traversal detected: {key}")

        return resolved

    async def store(self, key: str, data: bytes) -> None:
        """Store file data at the given key."""
        path = self._resolve_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)

        async with aiofiles.open(path, "wb") as f:
            await f.write(data)

        logger.debug(f"Stored {len(data)} bytes at {key}")

    async def retrieve(self, key: str) -> bytes:
        """Retrieve file data by key."""
        path = self._resolve_path(key)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {key}")

        async with aiofiles.open(path, "rb") as f:
            data = await f.read()

        return data

    async def stream(self, key: str, chunk_size: int = 8192) -> AsyncIterator[bytes]:
        """Stream file data in chunks for large file downloads."""
        path = self._resolve_path(key)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {key}")

        async with aiofiles.open(path, "rb") as f:
            while True:
                chunk = await f.read(chunk_size)
                if not chunk:
                    break
                yield chunk

    async def delete(self, key: str) -> None:
        """Delete file at the given key."""
        path = self._resolve_path(key)

        if path.exists():
            await aiofiles.os.remove(path)
            logger.debug(f"Deleted {key}")

            # Clean up empty parent directories
            parent = path.parent
            while parent != self.base_path:
                try:
                    parent.rmdir()  # Only removes if empty
                    parent = parent.parent
                except OSError:
                    break

    async def exists(self, key: str) -> bool:
        """Check if a file exists at the given key."""
        path = self._resolve_path(key)
        return path.exists()

    async def append_chunk(self, key: str, data: bytes) -> None:
        """Append a chunk of data to an existing file (for chunked uploads)."""
        path = self._resolve_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)

        async with aiofiles.open(path, "ab") as f:
            await f.write(data)

        logger.debug(f"Appended {len(data)} bytes to {key}")


# Singleton storage backend instance
_storage_backend: StorageBackend | None = None


def get_storage_backend() -> StorageBackend:
    """Get the configured storage backend (singleton)."""
    global _storage_backend

    if _storage_backend is None:
        settings = get_settings()

        if settings.storage_backend == "local":
            _storage_backend = LocalStorageBackend(settings.storage_local_path)
        else:
            raise ValueError(f"Unknown storage backend: {settings.storage_backend}")

    return _storage_backend
