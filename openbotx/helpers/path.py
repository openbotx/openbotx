from datetime import datetime
from pathlib import Path


def media_path(filename: str) -> str:
    """Generate a date-organized media storage path (public/media/YYYY/MM/DD/filename)."""
    today = datetime.now()
    return f"public/media/{today.year}/{today.month:02d}/{today.day:02d}/{filename}"


class PathResolver:
    """Resolves paths against a workspace with directory restriction enforcement."""

    def __init__(self, workspace: Path | None = None, allowed_dirs: list[Path] | None = None):
        self._workspace = workspace.resolve() if workspace else None
        self._allowed_dirs = [d.resolve() for d in allowed_dirs] if allowed_dirs else None

    @property
    def workspace(self) -> Path | None:
        return self._workspace

    @property
    def is_restricted(self) -> bool:
        return self._allowed_dirs is not None

    def resolve(self, path: str) -> Path:
        p = Path(path).expanduser()
        if not p.is_absolute() and self._workspace:
            p = self._workspace / p
        resolved = p.resolve()
        if self._allowed_dirs:
            for allowed in self._allowed_dirs:
                try:
                    resolved.relative_to(allowed)
                    return resolved
                except ValueError:
                    continue
            dirs = ", ".join(str(d) for d in self._allowed_dirs)
            raise PermissionError(f"Path {path} is outside allowed directories: {dirs}")
        return resolved
