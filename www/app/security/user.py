"""Defines security-related functions for authenticating users and verifying permissions."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2AuthorizationCodeBearer

from www.app.db import Crud
from www.app.errors import ItemNotFoundError, NotAuthenticatedError
from www.app.model import User
from www.app.security.requests import (
    get_request_api_key_id,
    maybe_get_request_api_key_id,
)


def verify_admin_permission(user: User, action_description: str = "perform this action") -> None:
    """Verifies that a user has admin permissions."""
    if not user.permissions or "is_admin" not in user.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=f"Only administrators can {action_description}"
        )


def verify_target_not_admin(user: User, action_description: str = "modify this user") -> None:
    """Verifies that a target user is not an admin."""
    if user.permissions and "is_admin" in user.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=f"Cannot {action_description} for admin users"
        )


async def get_session_user(
    crud: Annotated[Crud, Depends(Crud.get)],
    api_key_id: Annotated[str, Depends(get_request_api_key_id)],
) -> User:
    try:
        api_key = await crud.get_api_key(api_key_id)
        return await crud.get_user(api_key.user_id, throw_if_missing=True)
    except ItemNotFoundError:
        raise NotAuthenticatedError("Not authenticated")


async def get_session_user_with_permission(
    permission: str,
    crud: Crud,
    api_key_id: str,
) -> User:
    try:
        api_key = await crud.get_api_key(api_key_id)
        if api_key.permissions is None or permission not in api_key.permissions:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
        return await crud.get_user(api_key.user_id, throw_if_missing=True)
    except ItemNotFoundError:
        raise NotAuthenticatedError("Not authenticated")


async def get_session_user_with_read_permission(
    crud: Annotated[Crud, Depends(Crud.get)],
    api_key_id: Annotated[str, Depends(get_request_api_key_id)],
) -> User:
    return await get_session_user_with_permission("read", crud, api_key_id)


async def get_session_user_with_write_permission(
    crud: Annotated[Crud, Depends(Crud.get)],
    api_key_id: Annotated[str, Depends(get_request_api_key_id)],
) -> User:
    return await get_session_user_with_permission("write", crud, api_key_id)


async def get_session_user_with_admin_permission(user: Annotated[User, Depends(get_session_user)]) -> User:
    verify_admin_permission(user)
    return user


async def maybe_get_user_from_api_key(
    crud: Annotated[Crud, Depends(Crud.get)],
    api_key_id: Annotated[str | None, Depends(maybe_get_request_api_key_id)],
) -> User | None:
    if api_key_id is None:
        return None
    api_key = await crud.get_api_key(api_key_id)
    return await crud.get_user(api_key.user_id, throw_if_missing=False)
