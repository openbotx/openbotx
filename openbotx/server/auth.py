import datetime
import logging

import jwt
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

PUBLIC_PATHS = {
    "/api/auth/login",
    "/api/health",
}

PUBLIC_PREFIXES = (
    "/app",
    "/ws",
)


def create_token(username: str, secret: str) -> str:
    payload = {
        "sub": username,
        "exp": datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=24),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def verify_token(token: str, secret: str) -> dict | None:
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if path == "/":
            return await call_next(request)

        if path in PUBLIC_PATHS:
            return await call_next(request)

        for prefix in PUBLIC_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        if path.startswith("/api/"):
            secret = getattr(request.app.state, "auth_secret", "")
            if not secret:
                return await call_next(request)

            auth_header = request.headers.get("authorization", "")
            if not auth_header.startswith("Bearer "):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)

            token = auth_header[7:]
            payload = verify_token(token, secret)
            if not payload:
                return JSONResponse({"error": "Invalid token"}, status_code=401)

            request.state.user = payload.get("sub", "")

        return await call_next(request)
