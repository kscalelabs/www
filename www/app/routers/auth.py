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
        "GOOGLE_CLIENT_ID": settings.oauth.google_client_id,
        "GOOGLE_CLIENT_SECRET": settings.oauth.google_client_secret,
        "SECRET_KEY": settings.middleware.secret_key,
    },
)

oauth = OAuth(starlette_config)

# Register Google authentication.
google = oauth.register(
    name="google",
    client_id=settings.oauth.google_client_id,
    client_secret=settings.oauth.google_client_secret,
    access_token_url="https://accounts.google.com/o/oauth2/token",
    access_token_params=None,
    authorize_url="https://accounts.google.com/o/oauth2/auth",
    authorize_params={
        "scope": "openid email profile",
        "prompt": "consent",
    },
    api_base_url="https://www.googleapis.com/oauth2/v1/",
    client_kwargs={"scope": "openid email profile"},
)


@router.get("/login")
async def login_via_google(request: Request) -> RedirectResponse:
    redirect_uri = request.url_for("auth_callback")
    return await google.authorize_redirect(request, redirect_uri)


@router.get("/callback")
async def auth_callback(request: Request) -> RedirectResponse:
    token = await google.authorize_access_token(request)
    user_info = await google.parse_id_token(request, token)
    request.session["user"] = dict(user_info)
    return RedirectResponse(url="/profile")
