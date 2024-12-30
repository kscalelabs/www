"""Defines the API endpoint for authenticating the user."""

import logging
from typing import Annotated, Callable

import jwt
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, status
from fastapi.exceptions import HTTPException
from fastapi.requests import Request
from fastapi.responses import RedirectResponse
from pydantic.main import BaseModel
from starlette.config import Config as StarletteConfig

from www.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter()

starlette_config = StarletteConfig(
    environ={
        "COGNITO_CLIENT_ID": settings.oauth.cognito_client_id,
        "COGNITO_CLIENT_SECRET": settings.oauth.cognito_client_secret,
        "SECRET_KEY": settings.middleware.secret_key,
    },
)

oauth = OAuth(starlette_config)

cognito = oauth.register(
    name="oidc",
    authority=settings.oauth.cognito_authority,
    client_id=settings.oauth.cognito_client_id,
    client_secret=settings.oauth.cognito_client_secret,
    server_metadata_url=settings.oauth.server_metadata_url,
    client_kwargs={"scope": "openid email"},
)

jwks_client = jwt.PyJWKClient(settings.oauth.jwks_url)


class UserInfo(BaseModel):
    email: str
    email_verified: bool
    first_name: str
    last_name: str
    username: str


@router.get("/login")
async def login(request: Request) -> RedirectResponse:
    auth_redirect_uri = request.url_for("authorize")
    return await cognito.authorize_redirect(request, auth_redirect_uri)


@router.get("/logout")
async def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    redirect_url = request.url_for("index")
    return RedirectResponse(url=redirect_url)


@router.get("/authorize")
async def authorize(request: Request) -> RedirectResponse:
    token = await cognito.authorize_access_token(request)
    user = token["userinfo"]
    request.session["user"] = user
    redirect_url = request.url_for("index")
    return RedirectResponse(url=redirect_url)


class User(BaseModel):
    sub: str
    groups: list[str]
    email: str
    email_verified: bool
    username: str


async def get_user_from_request(request: Request) -> User | None:
    if "user" not in request.session:
        return None
    user = request.session["user"]
    return User(
        sub=user["sub"],
        groups=user["cognito:groups"],
        email=user["email"],
        email_verified=user["email_verified"],
        username=user["cognito:username"],
    )


async def require_user(request: Request) -> User:
    user = await get_user_from_request(request)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is not authenticated",
        )
    return user


def require_groups(required_groups: list[str]) -> Callable[[User], User]:
    def decorator(user: User) -> User:
        if not set(required_groups).issubset(user.groups):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User does not have required permissions",
            )
        return user

    return decorator


class ProfileResponse(BaseModel):
    email: str
    email_verified: bool
    username: str
    groups: list[str]


@router.get("/profile")
async def profile(user: Annotated[User, Depends(require_user)]) -> ProfileResponse:
    return ProfileResponse(
        email=user.email,
        email_verified=user.email_verified,
        username=user.username,
        groups=user.groups,
    )
