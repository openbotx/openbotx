import io
import logging
import shutil
import zipfile
from pathlib import Path

import httpx
from fastapi import APIRouter, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

MARKETPLACE_BASE_URL = "https://openbotx-marketplace.pages.dev/skills"


class InstallRequest(BaseModel):
    source: str
    name: str
    agent: str = ""


def _resolve_target_dir(request: Request, source: str, name: str, agent: str) -> Path:
    """Resolve install target: project (agent='') or agent workspace."""
    config = request.app.state.config
    project_path = config.project_path
    if not agent:
        return project_path / "skills" / source / name
    agent_cfg = config.agents.get(agent)
    if not agent_cfg:
        raise ValueError(f"Agent '{agent}' not found")
    workspace = agent_cfg.resolve_workspace(project_path)
    return workspace / "skills" / source / name


@router.get("/targets")
async def list_targets(request: Request):
    config = request.app.state.config
    targets = [{"label": "Project", "value": ""}]
    for name in config.agents:
        targets.append({"label": f"Agent: {name}", "value": name})
    return targets


@router.get("/check/{source}/{name}")
async def check_installed(source: str, name: str, request: Request, agent: str = ""):
    try:
        skill_dir = _resolve_target_dir(request, source, name, agent)
    except ValueError as e:
        return {"error": str(e)}
    installed = skill_dir.is_dir() and (skill_dir / "SKILL.md").exists()
    return {"installed": installed}


@router.post("/install")
async def install_skill(body: InstallRequest, request: Request):
    try:
        target_dir = _resolve_target_dir(request, body.source, body.name, body.agent)
    except ValueError as e:
        return {"error": str(e)}

    download_url = f"{MARKETPLACE_BASE_URL}/{body.source}/{body.name}/package.zip"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(download_url)
        if resp.status_code != 200:
            return {"error": f"Failed to download: HTTP {resp.status_code}"}

    if target_dir.exists():
        shutil.rmtree(target_dir)

    target_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        for member in zf.infolist():
            if member.is_dir():
                continue
            # normalize path: strip leading slashes and parent refs
            parts = Path(member.filename).parts
            safe_parts = [p for p in parts if p not in ("..", ".")]
            if not safe_parts:
                continue
            dest = target_dir / Path(*safe_parts)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(zf.read(member))

    target_label = f"agent:{body.agent}" if body.agent else "project"
    logger.info("installed marketplace skill %s/%s to %s", body.source, body.name, target_label)
    return {"ok": True}
