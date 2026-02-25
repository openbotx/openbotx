from fastapi import APIRouter, Request

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
            "requires": s.get("requires", []),
        }
        for s in skills
    ]


@router.get("/{name}")
async def get_skill(name: str, request: Request):
    skills_loader = request.app.state.skills_loader
    content = skills_loader.load_skill(name)
    if content is None:
        return {"error": "Skill not found"}
    return {"name": name, "content": content}
