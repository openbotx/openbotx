from fastapi import APIRouter, Request

router = APIRouter()


@router.get("")
async def list_agents(request: Request):
    config = request.app.state.config
    return [
        {
            "name": name,
            "description": agent.description,
            "model": agent.model,
        }
        for name, agent in config.agents.items()
    ]
