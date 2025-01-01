"""Defines authentication functionality."""

import logging
from typing import Annotated, Callable, Literal

from fastapi import Depends, Request, Security, status
from fastapi.exceptions import HTTPException
from fastapi.security import OpenIdConnect, SecurityScopes
from httpx import AsyncClient
from jwt import PyJWKClient, decode as jwt_decode
from pydantic.main import BaseModel

from www.settings import settings

logger = logging.getLogger(__name__)

oidc = OpenIdConnect(
    openIdConnectUrl=settings.oauth.server_metadata_url,
    auto_error=False,
)

jwks = PyJWKClient(settings.oauth.jwks_url)


class User(BaseModel):
    id: str
    is_admin: bool
    can_upload: bool
    can_test: bool


def _decode_user_from_token(token: str | None) -> User | None:
    if token is None:
        return None

    # Validates that the token is in the correct format.
    token_parts = token.split(" ")
    if len(token_parts) != 2 or token_parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
        )
    token_str = token_parts[1]

    try:
        # Get the signing key that matches the token
        signing_key = jwks.get_signing_key_from_jwt(token_str)

        claims = jwt_decode(
            token_str,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )

        groups = claims.get("cognito:groups", [])

        # Extract user information from claims and userinfo
        user = User(
            id=claims["sub"],
            is_admin="www-admin" in groups,
            can_upload="www-upload" in groups,
            can_test="www-test" in groups,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to validate token",
        ) from e

    if settings.site.is_test_environment and not user.can_test:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not have test permissions",
        )

    return user


async def get_user(
    security_scopes: SecurityScopes,
    token: Annotated[str | None, Depends(oidc)],
) -> User | None:
    """Gets the user from the OpenID Connect token.

    Args:
        security_scopes: The security scopes required for the endpoint
        token: The OpenID Connect token. If this is found, it is a string that
            looks like "Bearer <token>"

    Returns:
        The user information parsed from the OpenID Connect token, or None
        if no token was passed.
    """
    user = _decode_user_from_token(token)

    if user and security_scopes.scopes:
        for scope in security_scopes.scopes:
            if scope == "admin" and not user.is_admin:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions",
                    headers={"WWW-Authenticate": f"Bearer scope={security_scopes.scope_str}"},
                )
            elif scope == "upload" and not user.can_upload:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions",
                    headers={"WWW-Authenticate": f"Bearer scope={security_scopes.scope_str}"},
                )
    return user


async def require_user(user: Annotated[User | None, Depends(get_user)]) -> User:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is not authenticated",
        )
    return user


def require_permissions(permissions: set[Literal["admin", "upload"]]) -> Callable[[User], User]:
    async def dependency(user: Annotated[User, Security(get_user, scopes=list(permissions))]) -> User:
        return user

    return dependency


class UserInfo(BaseModel):
    email: str
    email_verified: bool


async def _decode_user_info_from_token(token: str | None) -> UserInfo | None:
    async with AsyncClient() as client:
        # Gets the metadata from the OpenID Connect server.
        metadata_response = await client.get(settings.oauth.server_metadata_url)
        metadata = metadata_response.json()
        if (userinfo_endpoint := metadata.get("userinfo_endpoint")) is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Userinfo endpoint not found in server metadata",
            )

        # Gets and parses the userinfo response.
        userinfo_response = await client.get(
            userinfo_endpoint,
            headers={"Authorization": token},
        )
        userinfo = userinfo_response.json()
        email = userinfo.get("email")
        email_verified_str = userinfo.get("email_verified")
        if not isinstance(email, str) or email_verified_str not in ("true", "false"):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Userinfo response is invalid",
            )

    userinfo = UserInfo(
        email=email,
        email_verified=email_verified_str == "true",
    )

    return userinfo


async def require_user_info(request: Request, token: Annotated[str | None, Depends(oidc)]) -> UserInfo:
    if "userinfo" in request.session:
        return UserInfo(**request.session["userinfo"])
    userinfo = await _decode_user_info_from_token(token)
    request.session["userinfo"] = userinfo.model_dump()
    return userinfo
