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
    config = request.app.state.config
    if body.username != config.auth.username or body.password != config.auth.password:
        return JSONResponse({"error": "Invalid credentials"}, status_code=401)

    token = create_token(body.username, config.auth.secret_key)
    return {"token": token, "username": body.username}
