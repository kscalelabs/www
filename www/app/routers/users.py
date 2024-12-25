"""Defines the API endpoint for creating, deleting and updating user information."""

import logging
from email.utils import parseaddr as parse_email_address
from typing import Annotated, Self

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic.main import BaseModel
from pydantic.networks import EmailStr

from www.app.crud.users import UserPublic
from www.app.db import Crud
from www.app.errors import ItemNotFoundError
from www.app.model import User, UserPermission
from www.app.security.requests import get_request_api_key_id
from www.app.security.user import (
    get_session_user_with_admin_permission,
    get_session_user_with_read_permission,
    get_session_user_with_write_permission,
    verify_admin_permission,
    verify_target_not_admin,
)

logger = logging.getLogger(__name__)

router = APIRouter()

TOKEN_TYPE = "Bearer"


def validate_email(email: str) -> str:
    try:
        email = parse_email_address(email)[1]
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email")
    return email


class UserSignup(BaseModel):
    signup_token_id: str
    email: str
    password: str


class MyUserInfoResponse(BaseModel):
    user_id: str
    email: str
    github_id: str | None
    google_id: str | None
    permissions: set[UserPermission] | None
    first_name: str | None
    last_name: str | None
    name: str | None
    bio: str | None

    @classmethod
    def from_user(cls, user: User) -> Self:
        return cls(
            user_id=user.id,
            email=user.email,
            google_id=user.google_id,
            github_id=user.github_id,
            permissions=user.permissions,
            first_name=user.first_name,
            last_name=user.last_name,
            name=user.name,
            bio=user.bio,
        )


@router.get("/me", response_model=MyUserInfoResponse)
async def get_user_info_endpoint(
    user: Annotated[User, Depends(get_session_user_with_read_permission)],
) -> MyUserInfoResponse | None:
    try:
        return MyUserInfoResponse(
            user_id=user.id,
            email=user.email,
            google_id=user.google_id,
            github_id=user.github_id,
            permissions=user.permissions,
            first_name=user.first_name,
            last_name=user.last_name,
            name=user.name,
            bio=user.bio,
        )
    except ValueError:
        return None


@router.delete("/me")
async def delete_user_endpoint(
    user: Annotated[User, Depends(get_session_user_with_write_permission)],
    crud: Annotated[Crud, Depends(Crud.get)],
) -> bool:
    await crud.delete_user(user.id)
    return True


class UserInfoResponseItem(BaseModel):
    id: str
    email: str

    @classmethod
    def from_user(cls, user: User) -> Self:
        return cls(
            id=user.id,
            email=user.email,
        )


class UsersInfoResponse(BaseModel):
    users: list[UserInfoResponseItem]


class PublicUserInfoResponseItem(BaseModel):
    id: str
    email: str
    username: str
    permissions: set[UserPermission] | None = None
    created_at: int | None = None
    updated_at: int | None = None
    first_name: str | None = None
    last_name: str | None = None
    name: str | None = None
    bio: str | None = None

    @classmethod
    def from_user(cls, user: User | UserPublic) -> Self:
        return cls(
            id=user.id,
            email=user.email,
            username=user.username,
            permissions=user.permissions,
            created_at=user.created_at,
            updated_at=user.updated_at,
            first_name=user.first_name,
            last_name=user.last_name,
            name=user.name,
            bio=user.bio,
        )


class PublicUsersInfoResponse(BaseModel):
    users: list[PublicUserInfoResponseItem]


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    user_id: str
    token: str


@router.get("/batch", response_model=PublicUsersInfoResponse)
async def get_users_batch_endpoint(
    crud: Annotated[Crud, Depends(Crud.get)],
    ids: list[str] = Query(...),
) -> PublicUsersInfoResponse:
    users = await crud.get_user_batch(ids)
    return PublicUsersInfoResponse(users=[PublicUserInfoResponseItem.from_user(user) for user in users])


@router.get("/public/batch", response_model=PublicUsersInfoResponse)
async def get_users_public_batch_endpoint(
    crud: Annotated[Crud, Depends(Crud.get)],
    ids: list[str] = Query(...),
) -> PublicUsersInfoResponse:
    users = await crud.get_user_batch(ids)
    return PublicUsersInfoResponse(users=[PublicUserInfoResponseItem.from_user(user) for user in users])


@router.get("/{id}", response_model=UserInfoResponseItem)
async def get_user_info_by_id_endpoint(id: str, crud: Annotated[Crud, Depends(Crud.get)]) -> UserInfoResponseItem:
    user = await crud.get_user(id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserInfoResponseItem.from_user(user)


@router.get("/public/me", response_model=UserPublic)
async def get_my_public_user_info_endpoint(
    user: User = Depends(get_session_user_with_read_permission),
) -> UserPublic:  # Change return type to UserPublic
    return UserPublic(**user.model_dump())  # Return UserPublic instance directly


@router.get("/public/{id}", response_model=UserPublic)
async def get_public_user_info_by_id_endpoint(
    id: str,
    crud: Annotated[Crud, Depends(Crud.get)],
) -> PublicUserInfoResponseItem:
    user = await crud.get_user_public(id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return PublicUserInfoResponseItem.from_user(user)


class UpdateUserRequest(BaseModel):
    github_id: str | None = None
    google_id: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    name: str | None = None
    bio: str | None = None


@router.put("/me", response_model=UserPublic)
async def update_profile(
    updates: UpdateUserRequest,
    user: Annotated[User, Depends(get_session_user_with_write_permission)],
    crud: Annotated[Crud, Depends(Crud.get)],
) -> UserPublic:
    try:
        update_dict = updates.model_dump(exclude_unset=True, exclude_none=True)
        updated_user = await crud.update_user(user.id, update_dict)
        return UserPublic(**updated_user.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Error updating profile: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating the profile.",
        )


class UpdateUsernameRequest(BaseModel):
    new_username: str


@router.put("/me/username", response_model=UserPublic)
async def update_username(
    request: UpdateUsernameRequest,
    user: Annotated[User, Depends(get_session_user_with_write_permission)],
    crud: Annotated[Crud, Depends(Crud.get)],
) -> UserPublic:
    if await crud.is_username_taken(request.new_username):
        raise HTTPException(status_code=400, detail="Username is already taken")
    updated_user = await crud.set_username(user.id, request.new_username)
    return UserPublic(**updated_user.model_dump())


@router.get("/validate-api-key")
async def validate_api_key_endpoint(
    crud: Annotated[Crud, Depends(Crud.get)],
    api_key_id: Annotated[str, Depends(get_request_api_key_id)],
) -> bool:
    try:
        await crud.get_api_key(api_key_id)
        return True
    except ItemNotFoundError:
        return False


class SetModeratorRequest(BaseModel):
    user_id: str
    is_mod: bool


@router.post("/set-moderator")
async def set_moderator(
    request: SetModeratorRequest,
    admin_user: Annotated[User, Depends(get_session_user_with_admin_permission)],
    crud: Annotated[Crud, Depends(Crud.get)],
) -> UserPublic:
    verify_admin_permission(admin_user, "modify moderator status")

    target_user = await crud.get_user(request.user_id, throw_if_missing=True)
    verify_target_not_admin(target_user, "modify moderator status")

    updated_user = await crud.set_moderator(request.user_id, request.is_mod)
    return UserPublic(**updated_user.model_dump())


@router.get("/check-username/{username}")
async def check_username_availability(
    username: str,
    crud: Annotated[Crud, Depends(Crud.get)],
) -> dict[str, bool]:
    logger.info("Checking if username %s is taken", username)
    is_taken = await crud.is_username_taken(username)
    return {"available": not is_taken}


class SetContentManagerRequest(BaseModel):
    user_id: str
    is_content_manager: bool


@router.post("/set-content-manager")
async def set_content_manager(
    request: SetContentManagerRequest,
    admin_user: Annotated[User, Depends(get_session_user_with_admin_permission)],
    crud: Annotated[Crud, Depends(Crud.get)],
) -> UserPublic:
    verify_admin_permission(admin_user, "modify content manager status")

    target_user = await crud.get_user(request.user_id, throw_if_missing=True)
    verify_target_not_admin(target_user, "modify content manager status")

    try:
        updated_user = await crud.set_content_manager(request.user_id, request.is_content_manager)
        return UserPublic(**updated_user.model_dump())
    except Exception as e:
        logger.error("Error setting content manager status: %s", e)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unable to update content manager status. Please verify the user exists and try again.",
        )
