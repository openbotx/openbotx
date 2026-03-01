from fastapi import APIRouter, Request
from pydantic import BaseModel

from openbotx.agent.skills import SkillsLoader

router = APIRouter()


def _get_loader(request: Request, agent: str) -> SkillsLoader:
    """Get a SkillsLoader for a specific context.

    - agent="": project only (builtin + project, no workspace)
    - agent="<name>": builtin + project + that agent's workspace
    """
    config = request.app.state.config
    project_path = config.project_path

    if not agent:
        return SkillsLoader(project_path)

    agent_cfg = config.agents.get(agent)
    if not agent_cfg:
        return request.app.state.skills_loader

    workspace = agent_cfg.resolve_workspace(project_path)
    return SkillsLoader(project_path, workspace)


def _tag_skills(skills: list[dict], agent: str) -> list[dict]:
    """Tag each skill with the agent it belongs to."""
    for s in skills:
        s["agent"] = agent if s["source"] == "workspace" else ""
    return skills


def _merge_all_skills(request: Request) -> list[dict]:
    """Merge all skills. Scans project and workspaces independently to avoid tier override."""
    config = request.app.state.config
    project_path = config.project_path
    result = []

    # builtin + project (no workspace tier)
    root_loader = SkillsLoader(project_path)
    for skill in root_loader.list_skills():
        skill["agent"] = ""
        result.append(skill)

    # workspace skills only, per unique workspace path
    seen_workspaces: dict[str, str] = {}
    for agent_name, agent_cfg in config.agents.items():
        workspace = agent_cfg.resolve_workspace(project_path)
        ws_key = str(workspace)
        if ws_key in seen_workspaces:
            continue
        seen_workspaces[ws_key] = agent_name

        loader = SkillsLoader(project_path, workspace)
        for skill in loader.list_skills():
            if skill["source"] == "workspace":
                skill["agent"] = agent_name
                result.append(skill)

    result.sort(key=lambda s: s["name"].split("/")[-1])
    return result


def _format_skill(s: dict) -> dict:
    return {
        "name": s["name"],
        "description": s.get("description", ""),
        "always": s.get("always", False),
        "source": s.get("source", "builtin"),
        "publisher": s.get("publisher", ""),
        "agent": s.get("agent", ""),
    }


@router.get("")
async def list_skills(request: Request, agent: str | None = None):
    if agent is None:
        skills = _merge_all_skills(request)
    else:
        loader = _get_loader(request, agent)
        skills = _tag_skills(loader.list_skills(), agent)

    return [_format_skill(s) for s in skills]


@router.get("/{name:path}")
async def get_skill(name: str, request: Request, agent: str = ""):
    loader = _get_loader(request, agent) if agent else request.app.state.skills_loader
    data = loader.load_skill_raw(name)
    if data is None:
        return {"error": "Skill not found"}
    return data


class SkillUpdate(BaseModel):
    content: str


@router.put("/{name:path}")
async def update_skill(name: str, body: SkillUpdate, request: Request, agent: str = ""):
    loader = _get_loader(request, agent) if agent else request.app.state.skills_loader
    error = loader.save_skill(name, body.content)
    if error:
        return {"error": error}
    return {"ok": True}


@router.delete("/{name:path}")
async def delete_skill(name: str, request: Request, agent: str = ""):
    loader = _get_loader(request, agent) if agent else request.app.state.skills_loader
    error = loader.delete_skill(name)
    if error:
        return {"error": error}
    return {"ok": True}
