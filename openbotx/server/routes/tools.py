from fastapi import APIRouter, Request

router = APIRouter()


@router.get("")
async def list_tools(request: Request):
    orchestrator = request.app.state.orchestrator
    definitions = orchestrator.get_tool_definitions()
    return [
        {
            "name": d["function"]["name"],
            "description": d["function"].get("description", ""),
            "parameters": d["function"].get("parameters", {}),
        }
        for d in definitions
    ]
