import logging
from starlette.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import asyncio
import os
import jwt
from jwt import PyJWKClient

logger = logging.getLogger(__name__)

JWKS_URL = f"{os.getenv("FRONTEND_URL")}/api/auth/jwks"
_jwks_client = PyJWKClient(JWKS_URL)

def _verify_token (token: str) -> str:
    signing_key = _jwks_client.get_signing_key_from_jwt(token)
    payload = jwt.decode(
        token,
        signing_key.key,
        algorithms=["EdDSA", "RS256"],
        audience=os.getenv("FRONTEND_URL"),
    )
    user_id = payload.get("sub") or payload.get("userId")
    if not user_id:
        raise ValueError("Token missing user id")
    return user_id

class AuthMiddleware (BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "Missing or invalid Authorization header"})

        token = auth_header.removeprefix("Bearer ").strip()
        logger.info("[LOAD-TEST-DEBUG] Incoming JWT for %s: %s", request.url.path, token)
        try:
            user_id = await asyncio.to_thread(_verify_token, token)
        except jwt.ExpiredSignatureError:
            return JSONResponse(status_code=401, content={"detail": "Token expired"})
        except Exception:
            return JSONResponse(status_code=401, content={"detail": "Invalid token"})

        request.state.user_id = user_id
        response = await call_next(request)
        return response
