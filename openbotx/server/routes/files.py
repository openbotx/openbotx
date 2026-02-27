import mimetypes
import posixpath

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from openbotx.storage.base import StorageProvider

router = APIRouter()

SYSTEM_FILES = {
    "Thumbs.db",
    "desktop.ini",
}

PROTECTED_FILES = {
    "config.yml",
    "config.yaml",
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
    parts = path.replace("\\", "/").split("/")
    return any(_is_hidden(part) for part in parts if part)


class AccessDeniedError(Exception):
    pass


def _is_protected(path: str) -> bool:
    return posixpath.normpath(path) in PROTECTED_FILES


def _safe_storage_path(path: str) -> str:
    normalized = posixpath.normpath(path)
    if normalized.startswith("..") or normalized.startswith("/"):
        raise AccessDeniedError("Access denied")
    if _has_hidden_component(normalized):
        raise AccessDeniedError("Access denied")
    return normalized


def _get_storage(request: Request) -> StorageProvider:
    return request.app.state.storage


def _classify_file(name: str) -> tuple[str, str | None]:
    mime, _ = mimetypes.guess_type(name)
    ext = posixpath.splitext(name)[1].lower()

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
    storage = _get_storage(request)

    async def _tree(dir_path: str) -> list[dict]:
        items = []
        try:
            entries = await storage.list_dir(dir_path)
        except Exception:
            return items
        for entry in entries:
            if _is_hidden(entry.name) or _is_protected(entry.path):
                continue
            if entry.is_dir:
                items.append(
                    {
                        "name": entry.name,
                        "path": entry.path,
                        "type": "directory",
                        "children": await _tree(entry.path),
                    }
                )
            else:
                items.append(
                    {
                        "name": entry.name,
                        "path": entry.path,
                        "type": "file",
                        "size": entry.size,
                    }
                )
        return items

    return await _tree("")


@router.get("/download/{path:path}")
async def download_file(path: str, request: Request):
    storage = _get_storage(request)
    try:
        safe_path = _safe_storage_path(path)
        if _is_protected(safe_path):
            return {"error": "Access denied"}
        if not await storage.exists(safe_path):
            return {"error": "File not found"}

        from openbotx.storage.local import LocalStorage

        if isinstance(storage, LocalStorage):
            file_path = storage._resolve(safe_path)
            return FileResponse(file_path)

        data = await storage.read(safe_path)
        mime, _ = mimetypes.guess_type(safe_path)
        return StreamingResponse(
            iter([data]),
            media_type=mime or "application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{posixpath.basename(safe_path)}"'
            },
        )
    except AccessDeniedError:
        return {"error": "Access denied"}


@router.post("/mkdir/{path:path}")
async def create_directory(path: str, request: Request):
    storage = _get_storage(request)
    try:
        safe_path = _safe_storage_path(path)
        await storage.create_dir(safe_path)
        return {"status": "ok", "path": safe_path}
    except AccessDeniedError:
        return {"error": "Access denied"}
    except Exception as e:
        return {"error": str(e)}


@router.post("/create/{path:path}")
async def create_file(path: str, request: Request):
    storage = _get_storage(request)
    try:
        safe_path = _safe_storage_path(path)
        if await storage.exists(safe_path):
            return {"error": "File already exists"}
        await storage.write(safe_path, b"")
        return {"status": "ok", "path": safe_path}
    except AccessDeniedError:
        return {"error": "Access denied"}
    except Exception as e:
        return {"error": str(e)}


@router.post("/upload/{path:path}")
async def upload_files(path: str, request: Request):
    storage = _get_storage(request)
    try:
        target_dir = _safe_storage_path(path) if path else ""
        form = await request.form()
        uploaded = []
        for key in form:
            file = form[key]
            if not hasattr(file, "read"):
                continue
            data = await file.read()
            filename = posixpath.basename(file.filename or "upload.bin")
            file_path = f"{target_dir}/{filename}" if target_dir else filename
            safe_path = _safe_storage_path(file_path)
            await storage.write(safe_path, data)
            uploaded.append(safe_path)
        return {"status": "ok", "paths": uploaded}
    except AccessDeniedError:
        return {"error": "Access denied"}
    except Exception as e:
        return {"error": str(e)}


@router.post("/upload")
async def upload_files_root(request: Request):
    return await upload_files("", request)


@router.get("/{path:path}")
async def read_file(path: str, request: Request):
    storage = _get_storage(request)
    try:
        safe_path = _safe_storage_path(path)
        if _is_protected(safe_path):
            return {"error": "Access denied"}
        if not await storage.exists(safe_path):
            return {"error": "File not found"}
        if await storage.is_directory(safe_path):
            return {"error": "Path is a directory"}

        file_type, mime = _classify_file(safe_path)

        if file_type == "text":
            data = await storage.read(safe_path)
            content = data.decode("utf-8")
            return {"path": safe_path, "type": "text", "content": content}

        file_size = await storage.size(safe_path)

        if safe_path.startswith("public/"):
            url = f"/{safe_path}"
        else:
            url = f"/api/files/download/{safe_path}"

        return {
            "path": safe_path,
            "type": file_type,
            "mime": mime,
            "size": file_size,
            "url": url,
        }
    except AccessDeniedError:
        return {"error": "Access denied"}
    except Exception as e:
        return {"error": str(e)}


@router.put("/{path:path}")
async def write_file(path: str, body: FileContent, request: Request):
    storage = _get_storage(request)
    try:
        safe_path = _safe_storage_path(path)
        if _is_protected(safe_path):
            return {"error": "This file can only be edited via Settings > Advanced"}
        await storage.write(safe_path, body.content.encode("utf-8"))
        return {"status": "ok", "path": safe_path}
    except AccessDeniedError:
        return {"error": "Access denied"}
    except Exception as e:
        return {"error": str(e)}


@router.delete("/{path:path}")
async def delete_path(path: str, request: Request):
    storage = _get_storage(request)
    try:
        safe_path = _safe_storage_path(path)
        if _is_protected(safe_path):
            return {"error": "This file cannot be deleted"}
        if not await storage.exists(safe_path):
            return {"error": "Not found"}

        if await storage.is_directory(safe_path):
            await storage.delete_dir(safe_path)
        else:
            await storage.delete(safe_path)
        return {"status": "deleted"}
    except AccessDeniedError:
        return {"error": "Access denied"}
    except Exception as e:
        return {"error": str(e)}
