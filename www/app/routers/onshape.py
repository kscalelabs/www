"""Defines the router endpoints for handling the Onshape flow."""

import json
import logging
from typing import Annotated, AsyncIterable

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from kol.onshape.config import ConverterConfig
from pydantic.main import BaseModel

from www.app.db import Crud
from www.app.model import User, can_write_listing
from www.app.auth import require_user

router = APIRouter()

logger = logging.getLogger(__name__)


class SetRequest(BaseModel):
    onshape_url: str | None


@router.post("/set/{listing_id}")
async def set_onshape_document(
    listing_id: str,
    request: SetRequest,
    user: Annotated[User, Depends(require_user)],
    crud: Annotated[Crud, Depends(Crud.get)],
) -> None:
    listing = await crud.get_listing(listing_id)
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    if not await can_write_listing(user, listing):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User cannot write to this listing")
    try:
        await crud.add_onshape_url_to_listing(listing_id, request.onshape_url)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


async def pull_onshape_document_generator(
    listing_id: str,
    user: User,
    crud: Crud,
    *,
    config: ConverterConfig | None = None,
) -> AsyncIterable[str]:
    # Gets the listing and makes sure the user has permission to write to it.
    listing = await crud.get_listing(listing_id)
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    if (onshape_url := listing.onshape_url) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No Onshape URL set for this listing")
    if not await can_write_listing(user, listing):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User cannot write to this listing")
    yield f"event: message\ndata: {json.dumps({'message': 'Starting download', 'level': 'success'})}\n\n"
    async for event in crud.download_onshape_document(listing, onshape_url, config=config):
        yield event
    yield "event: finish\ndata: finish\n\n"


@router.get("/pull/{listing_id}", response_class=StreamingResponse)
async def pull_onshape_document(
    listing_id: str,
    request: Request,
    crud: Annotated[Crud, Depends(Crud.get)],
    token: str | None = None,
    default_prismatic_joint_effort: float = 80.0,
    default_prismatic_joint_velocity: float = 5.0,
    default_revolute_joint_effort: float = 80.0,
    default_revolute_joint_velocity: float = 5.0,
    suffix_to_joint_effort: dict[str, float] | None = None,
    suffix_to_joint_velocity: dict[str, float] | None = None,
    voxel_size: float = 0.002,
    convex_collision_meshes: bool = False,
    add_mjcf: bool = True,
) -> StreamingResponse:
    # Because the default EventStream implementation doesn't provide an easy
    # way to pass the token in the header, we have to pass it as a query
    # parameter instead.
    if token is None:
        token = request.headers.get("Authorization") or request.headers.get("authorization")
        if token is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization header not found")
    api_key = await crud.get_api_key(token)
    if api_key.permissions is None or "write" not in api_key.permissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
    user = await crud.get_user(api_key.user_id, throw_if_missing=True)

    config = ConverterConfig(
        default_prismatic_joint_effort=default_prismatic_joint_effort,
        default_prismatic_joint_velocity=default_prismatic_joint_velocity,
        default_revolute_joint_effort=default_revolute_joint_effort,
        default_revolute_joint_velocity=default_revolute_joint_velocity,
        suffix_to_joint_effort=suffix_to_joint_effort or {},
        suffix_to_joint_velocity=suffix_to_joint_velocity or {},
        max_concurrent_requests=5,
        disable_mimics=True,
        voxel_size=voxel_size,
        convex_collision_meshes=convex_collision_meshes,
        add_mjcf=add_mjcf,
    )

    return StreamingResponse(
        content=pull_onshape_document_generator(listing_id, user, crud, config=config),
        media_type="text/event-stream",
    )
