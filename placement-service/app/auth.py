"""Login: checks a username and password and signs the JWT that all three services accept."""
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter

from app import config
from app.errors import ApiError
from app.schemas import ErrorResponse, LoginRequest, TokenResponse
from app.users import authenticate

router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse,
             responses={401: {"model": ErrorResponse}, 422: {"model": ErrorResponse}})
def login(data: LoginRequest):
    """Exchange a username and password for a signed HS256 token.

    Unknown user and wrong password give the same 401, so the answer does not
    reveal which usernames exist.
    """
    user = authenticate(data.username, data.password)
    if user is None:
        raise ApiError(401, "invalid_credentials", "Invalid username or password")
    now = datetime.now(timezone.utc)
    expires_in = config.jwt_ttl_minutes() * 60
    payload = {"sub": user.username, "role": user.role, "iat": now, "exp": now + timedelta(seconds=expires_in)}
    token = jwt.encode(payload, config.jwt_secret(), algorithm="HS256")
    return {"access_token": token, "token_type": "bearer", "expires_in": expires_in,
            "sub": user.username, "role": user.role, "name": user.name}