import os
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

def _user_or_ip_key(request: Request) -> str:
    user_id = getattr(request.state, "user_id", None)
    return user_id or get_remote_address(request)

limiter = Limiter(key_func=_user_or_ip_key, storage_uri=REDIS_URL)
