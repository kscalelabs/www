"""Defines the API endpoint for authenticating the user."""

import datetime
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.requests import Request
from pydantic.main import BaseModel

from www.auth import (
    COGNITO_AUTHORITY,
    COGNITO_CLIENT_ID,
    User,
    UserInfo,
    encode_api_key,
    require_user,
    require_user_info,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class UserResponse(BaseModel):
    user_id: str
    is_admin: bool
    can_upload: bool
    can_test: bool


@router.get("/user")
async def user(user: Annotated[User, Depends(require_user)]) -> UserResponse:
    return UserResponse(
        user_id=user.id,
        is_admin=user.is_admin,
        can_upload=user.can_upload,
        can_test=user.can_test,
    )


class ProfileResponse(BaseModel):
    email: str
    email_verified: bool
    user: UserResponse


@router.get("/profile")
async def profile(
    user: Annotated[UserResponse, Depends(user)],
    user_info: Annotated[UserInfo, Depends(require_user_info)],
) -> ProfileResponse:
    """Get the user's profile information.

    Since this require a second request to the OIDC userinfo endpoint, it will
    be slightly slower than the /user endpoint, so you should use it when you
    actually need the user's profile information.
    """
    return ProfileResponse(
        user=user,
        email=user_info.email,
        email_verified=user_info.email_verified,
    )


class APIKeyResponse(BaseModel):
    api_key: str


@router.post("/key")
async def create_api_key(
    user: Annotated[User, Depends(require_user)],
    user_info: Annotated[UserInfo, Depends(require_user_info)],
    num_hours: int = Query(default=24),
) -> APIKeyResponse:
    if num_hours < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Number of hours must be greater than 0",
        )
    if num_hours > 24:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Number of hours must be less than 24",
        )

    api_key = encode_api_key(
        user=user,
        user_info=user_info,
        exp_delta=datetime.timedelta(hours=num_hours),
    )
    return APIKeyResponse(api_key=api_key)


@router.get("/logout")
async def logout(request: Request, user: Annotated[User, Depends(require_user)]) -> bool:
    request.session.clear()
    return True


class OICDInfo(BaseModel):
    authority: str
    client_id: str


@router.get("/oicd")
async def oicd_info() -> OICDInfo:
    return OICDInfo(
        authority=COGNITO_AUTHORITY,
        client_id=COGNITO_CLIENT_ID,
    )
