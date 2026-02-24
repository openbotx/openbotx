from fastapi import APIRouter, Request
from pydantic import BaseModel
from pathlib import Path

router = APIRouter()

IGNORED_NAMES = {
    ".DS_Store", "Thumbs.db", "desktop.ini", ".thumbs",
    "__pycache__", ".git", ".svn", ".hg",
    ".pytest_cache", "__MACOSX", ".Spotlight-V100", ".Trashes",
    ".fseventsd", ".TemporaryItems",
}


class FileContent(BaseModel):
    content: str


def _get_workspace(request: Request) -> Path:
    return request.app.state.config.workspace_path


def _safe_path(workspace: Path, path: str) -> Path:
    resolved = (workspace / path).resolve()
    resolved.relative_to(workspace.resolve())
    return resolved


@router.get("")
async def list_files(request: Request):
    workspace = _get_workspace(request)

    def _tree(directory: Path) -> list[dict]:
        items = []
        if not directory.exists():
            return items
        try:
            entries = sorted(directory.iterdir())
        except PermissionError:
            return items
        for item in entries:
            if item.name in IGNORED_NAMES:
                continue
            rel = str(item.relative_to(workspace))
            try:
                if item.is_dir():
                    items.append({
                        "name": item.name,
                        "path": rel,
                        "type": "directory",
                        "children": _tree(item),
                    })
                else:
                    items.append({
                        "name": item.name,
                        "path": rel,
                        "type": "file",
                        "size": item.stat().st_size,
                    })
            except (PermissionError, OSError):
                continue
        return items

    return _tree(workspace)


@router.get("/{path:path}")
async def read_file(path: str, request: Request):
    workspace = _get_workspace(request)
    try:
        file_path = _safe_path(workspace, path)
        if not file_path.exists():
            return {"error": "File not found"}
        if file_path.is_dir():
            return {"error": "Path is a directory"}
        content = file_path.read_text(encoding="utf-8")
        return {"path": path, "content": content}
    except ValueError:
        return {"error": "Path outside workspace"}
    except Exception as e:
        return {"error": str(e)}


@router.put("/{path:path}")
async def write_file(path: str, body: FileContent, request: Request):
    workspace = _get_workspace(request)
    try:
        file_path = _safe_path(workspace, path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(body.content, encoding="utf-8")
        return {"status": "ok", "path": path}
    except ValueError:
        return {"error": "Path outside workspace"}
    except Exception as e:
        return {"error": str(e)}


@router.delete("/{path:path}")
async def delete_file(path: str, request: Request):
    workspace = _get_workspace(request)
    try:
        file_path = _safe_path(workspace, path)
        if not file_path.exists():
            return {"error": "File not found"}
        file_path.unlink()
        return {"status": "deleted"}
    except ValueError:
        return {"error": "Path outside workspace"}
    except Exception as e:
        return {"error": str(e)}
