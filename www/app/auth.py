"""Defines authentication functionality."""

import logging
from typing import Annotated, Callable, Literal

from fastapi import Depends, status, Request
from fastapi.exceptions import HTTPException
from pydantic.main import BaseModel
from fastapi.security import OpenIdConnect
from httpx import AsyncClient

from jwt import PyJWKClient, decode as jwt_decode

from www.settings import settings

logger = logging.getLogger(__name__)

oidc = OpenIdConnect(
    openIdConnectUrl=settings.oauth.server_metadata_url,
    auto_error=False,
)

jwks = PyJWKClient(settings.oauth.jwks_url)


class User(BaseModel):
    sub: str
    is_admin: bool
    is_content_manager: bool
    is_moderator: bool


async def get_user(
    token: Annotated[str | None, Depends(oidc)],
) -> User | None:
    """Gets the user from the OpenID Connect token.

    Args:
        token: The OpenID Connect token. If this is found, it is a string that
            looks like "Bearer <token>"

    Returns:
        The user information parsed from the OpenID Connect token, or None
        if no token was passed.
    """
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
        return User(
            sub=claims["sub"],
            is_admin="www-admin" in groups,
            is_content_manager="www-cm" in groups,
            is_moderator="www-mod" in groups,
        )

    except Exception as e:
        logger.warning(f"Failed to validate token or fetch user info: {e}")
        return None


async def require_user(user: Annotated[User | None, Depends(get_user)]) -> User:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is not authenticated",
        )
    return user


def require_permissions(permissions: set[Literal["admin", "content_manager", "moderator"]]) -> Callable[[User], User]:
    def decorator(user: Annotated[User, Depends(require_user)]) -> User:
        if (
            ("admin" in permissions and not user.is_admin)
            or ("content_manager" in permissions and not user.is_content_manager)
            or ("moderator" in permissions and not user.is_moderator)
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User does not have {permissions} permissions",
            )
        return user

    return decorator


class UserInfo(BaseModel):
    email: str
    email_verified: bool


async def require_user_info(
    request: Request,
    token: Annotated[str | None, Depends(oidc)],
    user: Annotated[User, Depends(require_user)],
) -> UserInfo:
    if "userinfo" in request.session:
        return UserInfo(**request.session["userinfo"])

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
        user=user,
    )

    request.session["userinfo"] = userinfo.model_dump()

    return userinfo
