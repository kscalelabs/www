"""Defines the router endpoints for handling listing artifacts."""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal, Self

from boto3.dynamodb.conditions import Key
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import RedirectResponse
from pydantic.main import BaseModel

from www.app.db import Crud
from www.app.model import (
    Artifact,
    ArtifactSize,
    ArtifactType,
    KernelArtifactType,
    Listing,
    User,
    can_write_artifact,
    can_write_listing,
    check_content_type,
    get_artifact_name,
    get_artifact_type,
    get_artifact_urls,
)
from www.app.security.user import (
    get_session_user_with_write_permission,
    maybe_get_user_from_api_key,
)
from www.app.utils.cloudfront_signer import CloudFrontUrlSigner
from www.settings import settings

router = APIRouter()

logger = logging.getLogger(__name__)


def _get_cloudfront_signer() -> CloudFrontUrlSigner | None:
    cld = settings.cloudfront
    if cld.key_id is None or cld.private_key is None:
        assert cld.key_id is None and cld.private_key is None, "Both key_id and private_key must be set!"
        return None
    return CloudFrontUrlSigner(key_id=cld.key_id, private_key=cld.private_key)


@router.get("/url/{artifact_type}/{listing_id}/{name}")
async def artifact_url(
    artifact_type: ArtifactType,
    listing_id: str,
    name: str,
    crud: Annotated[Crud, Depends(Crud.get)],
    size: ArtifactSize = "large",
) -> RedirectResponse:
    # First, get the artifact to retrieve its ID
    artifacts = await crud.get_listing_artifacts(
        listing_id,
        additional_filter_expression=Key("name").eq(name) & Key("artifact_type").eq(artifact_type),
    )

    if len(artifacts) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not find artifact associated with the given name and type",
        )
    artifact = artifacts[0]

    # Construct the S3 filename using the artifact ID
    _, file_extension = os.path.splitext(name)
    s3_filename = f"{artifact.id}{file_extension}"

    # Always use CloudFront domain and sign the URL
    base_url = f"https://{settings.cloudfront.domain}/{artifact.artifact_type}/{listing_id}/{s3_filename}"
    if size and artifact.artifact_type == "image":
        base_url = f"{base_url}_{size}"

    # Create and sign URL
    signer = _get_cloudfront_signer()
    if signer is None:
        return RedirectResponse(url=base_url)
    policy = signer.create_custom_policy(url=base_url, expire_days=180)
    signed_url = signer.generate_presigned_url(base_url, policy=policy)

    return RedirectResponse(url=signed_url)


class ArtifactUrls(BaseModel):
    small: str | None = None
    large: str
    expires_at: int


def get_artifact_url_response(artifact: Artifact) -> ArtifactUrls:
    artifact_urls = get_artifact_urls(artifact=artifact)
    expiration_time = None

    signer = _get_cloudfront_signer()
    if signer is not None:
        logger.debug("Original URLs for artifact %s: %s", artifact.id, artifact_urls)
        expire_days = 180
        expiration_time = int((datetime.utcnow() + timedelta(days=expire_days)).timestamp())

        sizes: list[Literal["small", "large"]] = ["small", "large"]
        for size in sizes:
            try:
                cf_url = (
                    f"https://{settings.cloudfront.domain}/{artifact.artifact_type}/{artifact.listing_id}/{artifact.id}"
                )
                if size == "small":
                    cf_url += "_small_256x256"
                elif size == "large":
                    cf_url += "_large_1536x1536"
                cf_url += f"_{artifact.name}"

                policy = signer.create_custom_policy(url=cf_url, expire_days=expire_days)
                artifact_urls[size] = signer.generate_presigned_url(cf_url, policy=policy)
            except KeyError:
                continue

    return ArtifactUrls(small=artifact_urls.get("small"), large=artifact_urls["large"], expires_at=expiration_time or 0)


class SingleArtifactResponse(BaseModel):
    artifact_id: str
    listing_id: str
    username: str
    slug: str
    name: str
    artifact_type: ArtifactType
    description: str | None
    timestamp: int
    urls: ArtifactUrls
    is_main: bool = False
    can_edit: bool = False
    size: int | None = None

    @classmethod
    async def from_artifact(
        cls,
        artifact: Artifact,
        crud: Crud | None = None,
        listing: Listing | None = None,
        creator: User | None = None,
        user: User | None = None,
    ) -> Self:

        async def get_creator(creator: User | None) -> User:
            if creator is None:
                if crud is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Could not find user associated with the given artifact",
                    )
                creator = await crud.get_user(artifact.user_id)
            if creator is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Could not find user associated with the given artifact",
                )
            return creator

        async def get_can_edit(user: User | None) -> bool:
            if user is None:
                return False
            return await can_write_artifact(user, artifact)

        async def get_listing(listing: Listing | None) -> Listing:
            if listing is None:
                if crud is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Could not find listing associated with the given artifact",
                    )
                listing = await crud.get_listing(artifact.listing_id)
            if listing is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Could not find listing associated with the given artifact",
                )
            return listing

        creator_non_null, can_edit, listing_non_null = await asyncio.gather(
            get_creator(creator),
            get_can_edit(user),
            get_listing(listing),
        )

        s3_filename = get_artifact_name(artifact=artifact)
        size = await crud.get_file_size(s3_filename) if crud is not None else None

        return cls(
            artifact_id=artifact.id,
            listing_id=artifact.listing_id,
            username=creator_non_null.username,
            slug=listing_non_null.slug,
            name=artifact.name,
            artifact_type=artifact.artifact_type,
            description=artifact.description,
            timestamp=artifact.timestamp,
            urls=get_artifact_url_response(artifact=artifact),
            is_main=artifact.is_main,
            can_edit=can_edit,
            size=size,
        )


class ListArtifactsResponse(BaseModel):
    artifacts: list[SingleArtifactResponse]


@router.get("/info/{artifact_id}")
async def get_artifact_info(
    artifact_id: str,
    user: Annotated[User | None, Depends(maybe_get_user_from_api_key)],
    crud: Annotated[Crud, Depends(Crud.get)],
) -> SingleArtifactResponse:
    artifact = await crud.get_raw_artifact(artifact_id)
    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not find artifact associated with the given id",
        )
    return await SingleArtifactResponse.from_artifact(artifact=artifact, crud=crud, user=user)


@router.get("/list/{listing_id}", response_model=ListArtifactsResponse)
async def list_artifacts(
    listing_id: str,
    crud: Annotated[Crud, Depends(Crud.get)],
) -> ListArtifactsResponse:
    listing, artifacts = await asyncio.gather(
        crud.get_listing(listing_id, throw_if_missing=True),
        crud.get_listing_artifacts(listing_id),
    )
    creator = await crud.get_user(listing.user_id)

    # Sort artifacts so that the main image comes first
    sorted_artifacts = sorted(artifacts, key=lambda x: not x.is_main)

    artifacts = await asyncio.gather(
        *(
            SingleArtifactResponse.from_artifact(
                artifact=artifact,
                crud=crud,
                listing=listing,
                creator=creator,
            )
            for artifact in sorted_artifacts
        )
    )

    return ListArtifactsResponse(artifacts=list(artifacts))


def validate_file(file: UploadFile) -> tuple[str, ArtifactType]:
    if file.filename is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Artifact filename was not provided",
        )
    if file.size is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Artifact size was not provided",
        )
    if file.size < settings.artifact.min_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Artifact size is too small; {file.size} is less than {settings.artifact.min_bytes} bytes",
        )
    if file.size > settings.artifact.max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Artifact size is too large; {file.size} is greater than {settings.artifact.max_bytes} bytes",
        )

    # Parses the artifact type from the content type and filename.
    artifact_type = get_artifact_type(file.content_type, file.filename)
    check_content_type(file.content_type, artifact_type)

    return file.filename, artifact_type


class UploadArtifactResponse(BaseModel):
    artifacts: list[SingleArtifactResponse]


@router.post("/upload/{listing_id}", response_model=UploadArtifactResponse)
async def upload(
    listing_id: str,
    user: Annotated[User, Depends(get_session_user_with_write_permission)],
    crud: Annotated[Crud, Depends(Crud.get)],
    files: list[UploadFile],
) -> UploadArtifactResponse:
    # Checks that the user is not uploading too many files at once.
    if len(files) > settings.artifact.max_concurrent_file_uploads:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Too many files were uploaded concurrently",
        )
    filenames = [validate_file(file) for file in files]

    # Makes sure that filenames are unique.
    if len(set(filename for filename, _ in filenames)) != len(filenames):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Duplicate filenames were provided",
        )

    # Checks that the listing is valid.
    listing = await crud.get_listing(listing_id)

    if listing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not find listing associated with the given id",
        )
    if not await can_write_listing(user, listing):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not have permission to upload artifacts to this listing",
        )

    # Uploads the artifacts in chunks and adds them to the listing.
    artifacts = await asyncio.gather(
        *(
            crud.upload_artifact(
                name=filename,
                file=file,
                listing=listing,
                artifact_type=artifact_type,
            )
            for file, (filename, artifact_type) in zip(files, filenames)
        )
    )

    artifact_responses = await asyncio.gather(
        *(
            SingleArtifactResponse.from_artifact(
                artifact=artifact,
                crud=crud,
                listing=listing,
                creator=user,
            )
            for artifact in artifacts
        )
    )

    return UploadArtifactResponse(artifacts=list(artifact_responses))


class UpdateArtifactRequest(BaseModel):
    name: str | None = None
    description: str | None = None


@router.put("/edit/{artifact_id}", response_model=bool)
async def edit_artifact(
    id: str,
    artifact: UpdateArtifactRequest,
    user: Annotated[User, Depends(get_session_user_with_write_permission)],
    crud: Annotated[Crud, Depends(Crud.get)],
) -> bool:
    artifact_info = await crud.get_raw_artifact(id)
    if artifact_info is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")
    if not await can_write_artifact(user, artifact_info):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to edit this artifact",
        )
    await crud.edit_artifact(artifact_id=id, name=artifact.name, description=artifact.description)
    return True


@router.delete("/delete/{artifact_id}", response_model=bool)
async def delete_artifact(
    artifact_id: str,
    user: Annotated[User, Depends(get_session_user_with_write_permission)],
    crud: Annotated[Crud, Depends(Crud.get)],
) -> bool:
    artifact = await crud.get_raw_artifact(artifact_id)
    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not find artifact associated with the given id",
        )
    if not await can_write_artifact(user, artifact):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not have permission to delete this artifact",
        )
    await crud.remove_artifact(artifact)
    return True


@router.put("/list/{listing_id}/main", response_model=bool)
async def set_main_image(
    listing_id: str,
    artifact_id: str,
    user: Annotated[User, Depends(get_session_user_with_write_permission)],
    crud: Annotated[Crud, Depends(Crud.get)],
) -> bool:
    listing = await crud.get_listing(listing_id)
    if listing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found",
        )
    if not await can_write_listing(user, listing):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not have permission to edit this listing",
        )

    await crud.set_main_image(listing_id, artifact_id)
    return True


class PresignedUrlResponse(BaseModel):
    upload_url: str
    artifact_id: str


@router.post("/presigned/{listing_id}", response_model=PresignedUrlResponse)
async def get_presigned_url(
    listing_id: str,
    filename: str,
    user: Annotated[User, Depends(get_session_user_with_write_permission)],
    crud: Annotated[Crud, Depends(Crud.get)],
) -> PresignedUrlResponse:
    if not filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename was not provided",
        )

    user_permissions = user.permissions or set()
    if not ("is_admin" in user_permissions or "is_verified_member" in user_permissions):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Only verified members and admins can upload kernel images"
        )

    if not Path(filename).suffix.lower() == ".img":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Only .img files are supported for kernel uploads"
        )

    artifact_type: KernelArtifactType = "kernel"

    listing = await crud.get_listing(listing_id)
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Could not find listing")
    if not await can_write_listing(user, listing):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No permission to upload")

    artifact = Artifact.create(
        user_id=listing.user_id,
        listing_id=listing.id,
        name=filename,
        artifact_type=artifact_type,
    )
    await crud._add_item(artifact)

    try:
        s3_filename = get_artifact_name(artifact=artifact)

        presigned_url = await crud.generate_presigned_upload_url(
            filename=filename,
            s3_key=s3_filename,
            content_type="application/x-raw-disk-image",
        )

        return PresignedUrlResponse(upload_url=presigned_url, artifact_id=artifact.id)

    except Exception as e:
        await crud._delete_item(artifact)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
