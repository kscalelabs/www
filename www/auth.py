"""Defines authentication functionality."""

import datetime
import logging
from typing import Annotated, Any, Callable, Coroutine, Literal

from fastapi import Depends, Request, Security, status
from fastapi.exceptions import HTTPException
from fastapi.security import APIKeyHeader, OpenIdConnect, SecurityScopes
from httpx import AsyncClient
from jwt import PyJWKClient, decode as jwt_decode, encode as jwt_encode
from pydantic.main import BaseModel

from www.settings import env

logger = logging.getLogger(__name__)

# Points to the Cognito authority information page.
COGNITO_AUTHORITY = "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_dqtJl1Iew"
COGNITO_CLIENT_ID = "5lu9h7nhtf6dvlunpodjr9qil5"

SERVER_METADATA_URL = f"{COGNITO_AUTHORITY}/.well-known/openid-configuration"
JWKS_URL = f"{COGNITO_AUTHORITY}/.well-known/jwks.json"

HEADER_NAME = "x-kscale-api-key"

oidc = OpenIdConnect(
    openIdConnectUrl=SERVER_METADATA_URL,
    auto_error=False,
)

api_key = APIKeyHeader(
    name=HEADER_NAME,
    auto_error=False,
)

jwks = PyJWKClient(JWKS_URL)


class User(BaseModel):
    id: str
    is_admin: bool
    can_upload: bool
    can_test: bool


class UserInfo(BaseModel):
    email: str
    email_verified: bool


def encode_api_key(user: User, user_info: UserInfo, exp_delta: datetime.timedelta) -> str:
    """Returns a new API key for a user.

    Args:
        user: The user to get the API key for
        user_info: The user info to get the API key for
        exp_delta: The expiration delta for the API key

    Returns:
        A new API key for the user
    """
    groups = []
    if user.is_admin:
        groups.append("admin")
    if user.can_upload:
        groups.append("upload")
    if user.can_test:
        groups.append("test")

    return jwt_encode(
        {
            "sub": user.id,
            "groups": groups,
            "email": user_info.email,
            "email_verified": user_info.email_verified,
            "exp": datetime.datetime.now(datetime.UTC) + exp_delta,
        },
        env.middleware.secret_key,
        algorithm="HS256",
    )


def _decode_user_info_from_api_key(api_key: str) -> tuple[User, UserInfo]:
    data = jwt_decode(api_key, env.middleware.secret_key, algorithms=["HS256"])

    user = User(
        id=data["sub"],
        is_admin="admin" in data["groups"],
        can_upload="upload" in data["groups"],
        can_test="test" in data["groups"],
    )

    user_info = UserInfo(
        email=data["email"],
        email_verified=data["email_verified"],
    )

    return user, user_info


def _decode_user_from_token(token: str) -> User:
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
            status_code=status.HTTP_401_UNAUTHORIZED,  # Return 401 to indicate that the token is invalid
            detail="Failed to validate token",
        ) from e

    if env.site.is_test_environment and not user.can_test:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,  # Return 403 to indicate that the user does not have permissions
            detail="User does not have test permissions",
        )

    return user


async def get_user(
    security_scopes: SecurityScopes,
    token: Annotated[str | None, Depends(oidc)],
    api_key: Annotated[str | None, Depends(api_key)],
) -> User | None:
    """Gets the user from the OpenID Connect token.

    Args:
        security_scopes: The security scopes required for the endpoint
        token: The OpenID Connect token. If this is found, it is a string that
            looks like "Bearer <token>"
        api_key: The API key. If this is found, it is a string that looks like
            "Bearer <api_key>"

    Returns:
        The user information parsed from the OpenID Connect token, or None
        if no token was passed.
    """
    if token is not None:
        user = _decode_user_from_token(token)
    elif api_key is not None:
        user, _ = _decode_user_info_from_api_key(api_key)
    else:
        return None

    # Checks security scopes.
    if security_scopes.scopes:
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


def require_permissions(permissions: set[Literal["admin", "upload"]]) -> Callable[[User], Coroutine[Any, Any, User]]:
    async def dependency(user: Annotated[User, Security(get_user, scopes=list(permissions))]) -> User:
        return user

    return dependency


async def _decode_user_info_from_token(token: Annotated[str, Depends(oidc)]) -> UserInfo:
    async with AsyncClient() as client:
        # Gets the metadata from the OpenID Connect server.
        metadata_response = await client.get(SERVER_METADATA_URL)
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


async def require_user_info(
    request: Request,
    token: Annotated[str | None, Depends(oidc)],
    api_key: Annotated[str | None, Depends(api_key)],
) -> UserInfo:
    if "userinfo" in request.session:
        return UserInfo(**request.session["userinfo"])
    if token is not None:
        userinfo = await _decode_user_info_from_token(token)
        request.session["userinfo"] = userinfo.model_dump()
    elif api_key is not None:
        _, userinfo = _decode_user_info_from_api_key(api_key)
        request.session["userinfo"] = userinfo.model_dump()
    else:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is not authenticated")
    return userinfo
