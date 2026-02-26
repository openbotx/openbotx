from pathlib import Path


class PathResolver:
    """Resolves paths against a workspace with directory restriction enforcement."""

    def __init__(self, workspace: Path | None = None, allowed_dirs: list[Path] | None = None):
        self._workspace = workspace
        self._allowed_dirs = allowed_dirs

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
                    resolved.relative_to(allowed.resolve())
                    return resolved
                except ValueError:
                    continue
            dirs = ", ".join(str(d) for d in self._allowed_dirs)
            raise PermissionError(f"Path {path} is outside allowed directories: {dirs}")
        return resolved
