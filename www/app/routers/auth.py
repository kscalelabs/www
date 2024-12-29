"""Defines the API endpoint for authenticating the user."""

import logging

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter
from fastapi.requests import Request
from fastapi.responses import RedirectResponse
from starlette.config import Config as StarletteConfig

from www.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# Set up authlib OAuth.
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
    server_metadata_url=settings.oauth.cognito_metadata_url,
    client_kwargs={"scope": "phone openid email"},
)


@router.get("/login")
async def login_via_google(request: Request) -> RedirectResponse:
    redirect_uri = request.url_for("auth_callback")
    return await cognito.authorize_redirect(request, redirect_uri)


@router.get("/authorize")
async def auth_callback(request: Request) -> RedirectResponse:
    token = await cognito.authorize_access_token(request)
    user_info = await cognito.parse_id_token(request, token)
    request.session["user"] = dict(user_info)
    return RedirectResponse(url="/profile")
