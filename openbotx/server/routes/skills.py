from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


@router.get("")
async def list_skills(request: Request):
    skills_loader = request.app.state.skills_loader
    skills = skills_loader.list_skills()
    return [
        {
            "name": s["name"],
            "description": s.get("description", ""),
            "always": s.get("always", False),
            "source": s.get("source", "project"),
        }
        for s in skills
    ]


@router.get("/{name}")
async def get_skill(name: str, request: Request):
    skills_loader = request.app.state.skills_loader
    data = skills_loader.load_skill_raw(name)
    if data is None:
        return {"error": "Skill not found"}
    return data


class SkillUpdate(BaseModel):
    content: str


@router.put("/{name}")
async def update_skill(name: str, body: SkillUpdate, request: Request):
    skills_loader = request.app.state.skills_loader
    error = skills_loader.save_skill(name, body.content)
    if error:
        return {"error": error}
    return {"ok": True}
