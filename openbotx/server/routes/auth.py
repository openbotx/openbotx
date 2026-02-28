from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from openbotx.server.auth import create_token

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login(body: LoginRequest, request: Request):
    auth_config = request.app.state.auth_config
    if not auth_config:
        return JSONResponse({"error": "Auth not configured"}, status_code=500)
    if body.username != auth_config.username or body.password != auth_config.password:
        return JSONResponse({"error": "Invalid credentials"}, status_code=401)

    token = create_token(body.username, request.app.state.auth_secret)
    return {"token": token, "username": body.username}
