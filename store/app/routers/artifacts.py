"""Defines the router endpoints for handling listing artifacts."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from fastapi.responses import RedirectResponse
from pydantic.main import BaseModel

from store.app.db import Crud
from store.app.model import UPLOAD_CONTENT_TYPE_OPTIONS, ArtifactSize, ArtifactType, User, get_artifact_url
from store.app.routers.users import get_session_user_with_write_permission

artifacts_router = APIRouter()

logger = logging.getLogger(__name__)


class UploadImageResponse(BaseModel):
    image_id: str


@artifacts_router.get("/url/{artifact_type}/{artifact_id}")
async def artifact_url(
    artifact_type: ArtifactType,
    artifact_id: str,
    size: ArtifactSize = "large",
) -> RedirectResponse:
    # TODO: Use CloudFront API to return a signed CloudFront URL.
    return RedirectResponse(url=get_artifact_url(artifact_id, artifact_type, size))


class ListArtifactsItem(BaseModel):
    artifact_id: str
    artifact_type: ArtifactType
    description: str | None
    timestamp: int
    url: str


class ListArtifactsResponse(BaseModel):
    artifacts: list[ListArtifactsItem]


@artifacts_router.get("/{listing_id}", response_model=ListArtifactsResponse)
async def list_artifacts(listing_id: str, crud: Annotated[Crud, Depends(Crud.get)]) -> ListArtifactsResponse:
    return ListArtifactsResponse(
        artifacts=[
            ListArtifactsItem(
                artifact_id=artifact.id,
                artifact_type=artifact.artifact_type,
                description=artifact.description,
                timestamp=artifact.timestamp,
                url=get_artifact_url(artifact.id, artifact.artifact_type),
            )
            for artifact in await crud.get_listing_artifacts(listing_id)
        ],
    )


class UploadArtifactRequest(BaseModel):
    artifact_type: ArtifactType
    listing_id: str
    description: str | None = None


class UploadArtifactResponse(BaseModel):
    artifact_id: str


@artifacts_router.post("/upload", response_model=UploadArtifactResponse)
async def upload(
    user: Annotated[User, Depends(get_session_user_with_write_permission)],
    crud: Annotated[Crud, Depends(Crud.get)],
    file: UploadFile,
    metadata: Annotated[str, Form()],
) -> UploadArtifactResponse:
    if file.filename is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URDF filename was not provided",
        )

    # Converts the metadata JSON string to a Pydantic model.
    data = UploadArtifactRequest.model_validate_json(metadata)

    # Checks that the content type is valid.
    if (content_type := file.content_type) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URDF content type was not provided",
        )
    if content_type not in UPLOAD_CONTENT_TYPE_OPTIONS[data.artifact_type]:
        content_type_options_string = ", ".join(UPLOAD_CONTENT_TYPE_OPTIONS[data.artifact_type])
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid content type {content_type}; expected one of {content_type_options_string}",
        )

    # Checks that the listing is valid.
    listing = await crud.get_listing(data.listing_id)
    if listing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not find listing associated with the given id",
        )

    # Uploads the URDF and adds it to the listing.
    artifact = await crud.upload_artifact(
        file=file.file,
        name=file.filename,
        listing=listing,
        user_id=user.id,
        artifact_type=data.artifact_type,
        description=data.description,
    )
    return UploadArtifactResponse(artifact_id=artifact.id)


@artifacts_router.delete("/delete/{artifact_id}", response_model=bool)
async def delete(
    user: Annotated[User, Depends(get_session_user_with_write_permission)],
    crud: Annotated[Crud, Depends(Crud.get)],
    artifact_id: str,
) -> bool:
    artifact = await crud.get_raw_artifact(artifact_id)
    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not find URDF associated with the given id",
        )

    # Deletes the URDF from the listing.
    await crud.remove_artifact(artifact, user.id)

    return True