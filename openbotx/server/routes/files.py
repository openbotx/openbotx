import mimetypes
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

router = APIRouter()

SYSTEM_FILES = {
    "Thumbs.db",
    "desktop.ini",
}

EDITABLE_EXTENSIONS = {
    ".md",
    ".yml",
    ".yaml",
    ".txt",
    ".json",
    ".xml",
    ".html",
    ".htm",
    ".css",
    ".js",
    ".ts",
    ".py",
    ".sh",
    ".toml",
    ".cfg",
    ".ini",
    ".csv",
    ".env",
    ".log",
}


class FileContent(BaseModel):
    content: str


def _is_hidden(name: str) -> bool:
    return name.startswith(".") or name in SYSTEM_FILES


def _has_hidden_component(path: str) -> bool:
    return any(_is_hidden(part) for part in Path(path).parts)


def _get_project_root(request: Request) -> Path:
    return request.app.state.config.project_path


class AccessDeniedError(Exception):
    pass


def _safe_path(root: Path, path: str) -> Path:
    if _has_hidden_component(path):
        raise AccessDeniedError("Access denied")
    resolved = (root / path).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        raise AccessDeniedError("Access denied")
    return resolved


def _classify_file(file_path: Path) -> tuple[str, str | None]:
    mime, _ = mimetypes.guess_type(file_path.name)
    ext = file_path.suffix.lower()

    if ext in EDITABLE_EXTENSIONS or (mime and mime.startswith("text/")):
        return "text", mime
    if mime and mime.startswith("image/"):
        return "image", mime
    if mime and mime.startswith("video/"):
        return "video", mime
    if mime and mime.startswith("audio/"):
        return "audio", mime
    return "binary", mime


@router.get("")
async def list_files(request: Request):
    root = _get_project_root(request)

    def _tree(directory: Path) -> list[dict]:
        items = []
        if not directory.exists():
            return items
        try:
            entries = sorted(directory.iterdir())
        except PermissionError:
            return items
        for item in entries:
            if _is_hidden(item.name):
                continue
            rel = str(item.relative_to(root))
            try:
                if item.is_dir():
                    items.append(
                        {
                            "name": item.name,
                            "path": rel,
                            "type": "directory",
                            "children": _tree(item),
                        }
                    )
                else:
                    items.append(
                        {
                            "name": item.name,
                            "path": rel,
                            "type": "file",
                            "size": item.stat().st_size,
                        }
                    )
            except (PermissionError, OSError):
                continue
        return items

    return _tree(root)


@router.get("/download/{path:path}")
async def download_file(path: str, request: Request):
    root = _get_project_root(request)
    try:
        file_path = _safe_path(root, path)
        if not file_path.exists():
            return {"error": "File not found"}
        return FileResponse(file_path)
    except AccessDeniedError:
        return {"error": "Access denied"}


@router.get("/{path:path}")
async def read_file(path: str, request: Request):
    root = _get_project_root(request)
    try:
        file_path = _safe_path(root, path)
        if not file_path.exists():
            return {"error": "File not found"}
        if file_path.is_dir():
            return {"error": "Path is a directory"}

        file_type, mime = _classify_file(file_path)

        if file_type == "text":
            content = file_path.read_text(encoding="utf-8")
            return {"path": path, "type": "text", "content": content}

        if path.startswith("public/"):
            url = f"/{path}"
        else:
            url = f"/api/files/download/{path}"

        return {
            "path": path,
            "type": file_type,
            "mime": mime,
            "size": file_path.stat().st_size,
            "url": url,
        }
    except AccessDeniedError:
        return {"error": "Access denied"}
    except Exception as e:
        return {"error": str(e)}


@router.put("/{path:path}")
async def write_file(path: str, body: FileContent, request: Request):
    root = _get_project_root(request)
    try:
        file_path = _safe_path(root, path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(body.content, encoding="utf-8")
        return {"status": "ok", "path": path}
    except AccessDeniedError:
        return {"error": "Access denied"}
    except Exception as e:
        return {"error": str(e)}


@router.delete("/{path:path}")
async def delete_file(path: str, request: Request):
    root = _get_project_root(request)
    try:
        file_path = _safe_path(root, path)
        if not file_path.exists():
            return {"error": "File not found"}
        file_path.unlink()
        return {"status": "deleted"}
    except AccessDeniedError:
        return {"error": "Access denied"}
    except Exception as e:
        return {"error": str(e)}
