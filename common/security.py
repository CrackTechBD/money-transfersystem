import time, jwt
from typing import Dict, Optional
from common.settings import settings

ALGO = "HS256"

def mint_user_jwt(sub: str, claims: Optional[Dict] = None) -> str:
    now = int(time.time())
    payload = {
        "iss": settings.jwt_issuer,
        "sub": sub,
        "iat": now,
        "exp": now + settings.jwt_ttl_seconds,
        **(claims or {}),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGO)

def mint_internal_jwt(aud: str, claims: Optional[Dict] = None) -> str:
    now = int(time.time())
    payload = {
        "iss": settings.jwt_issuer,
        "aud": aud,
        "iat": now,
        "exp": now + settings.internal_jwt_ttl_seconds,
        **(claims or {}),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGO)

def verify_token(token: str, audience: Optional[str] = None) -> Dict:
    options = {"require": ["exp", "iat", "iss"]}
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[ALGO],
        audience=audience,
        options=options,
        issuer=settings.jwt_issuer,
    )
