"""Defines CRUD interface for handling user-uploaded artifacts."""

import asyncio
import io
import logging
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import IO, Any, AsyncIterator, Literal
from xml.etree import ElementTree as ET

import trimesh
from boto3.dynamodb.conditions import ComparisonCondition
from fastapi import UploadFile
from PIL import Image

from www.app.crud.base import BaseDbCrud, ItemNotFoundError
from www.app.errors import BadArtifactError
from www.app.model import (
    DOWNLOAD_CONTENT_TYPE,
    Artifact,
    ArtifactSize,
    ArtifactType,
    Listing,
    SizeMapping,
    get_artifact_name,
)
from www.settings import settings
from www.utils import save_xml

logger = logging.getLogger(__name__)


class ArtifactsCrud(BaseDbCrud):
    """CRUD operations for Artifacts."""

    def _get_table_name(self) -> str:
        return "artifacts"

    @classmethod
    def get_gsis(cls) -> set[str]:
        return super().get_gsis().union({"user_id", "listing_id", "name"})

    async def create_artifact(self, **artifact_data: Any) -> Artifact:
        # Verify listing exists
        listing = await self._get_item(artifact_data["listing_id"], Listing)
        if not listing:
            raise ItemNotFoundError(f"Listing with ID {artifact_data['listing_id']} not found")

        artifact = Artifact.create(**artifact_data)
        await self._add_item(artifact)
        return artifact

    async def get_artifact(self, artifact_id: str) -> Artifact:
        artifact = await self._get_item(artifact_id, Artifact)
        if not artifact:
            raise ItemNotFoundError("Artifact not found")
        return artifact

    async def update_artifact(self, artifact_id: str, update_data: dict[str, Any]) -> Artifact:
        artifact = await self.get_artifact(artifact_id)
        if not artifact:
            raise ItemNotFoundError("Artifact not found")

        await self._update_item(artifact_id, Artifact, update_data)
        updated_artifact = await self.get_artifact(artifact_id)
        return updated_artifact

    async def delete_artifact(self, artifact: Artifact) -> None:
        await self._delete_item(artifact)

    async def iter_archive(
        self,
        file: UploadFile,
        artifact_type: Literal["tgz", "zip"],
    ) -> AsyncIterator[tuple[bytes, str]]:
        file_input = io.BytesIO(await file.read())
        match artifact_type:
            case "tgz":
                tar_archive = tarfile.open(fileobj=file_input, mode="r:gz")
                for tar_member in tar_archive.getmembers():
                    if tar_member.isfile():
                        if (member_read := tar_archive.extractfile(tar_member)) is None:
                            continue
                        file_data = member_read.read()
                        yield file_data, tar_member.name
            case "zip":
                zip_archive = zipfile.ZipFile(file_input)
                for zip_member in zip_archive.namelist():
                    if not zip_member.endswith("/"):
                        file_data = zip_archive.read(zip_member)
                        yield file_data, zip_member
            case _:
                raise BadArtifactError(f"Invalid archive type: {artifact_type}")

    async def _crop_image(self, image: Image.Image, size: tuple[int, int]) -> IO[bytes]:
        # Simply squashes the image to the desired size.
        # image_resized = image.resize(size, resample=Image.Resampling.BICUBIC)
        # Finds a bounding box of the image and crops it to the desired size.
        image_ratio, size_ratio = image.width / image.height, size[0] / size[1]
        if image_ratio > size_ratio:
            new_width = int(image.height * size_ratio)
            new_height = image.height
            left = (image.width - new_width) // 2
            upper = 0
        else:
            new_width = image.width
            new_height = int(image.width / size_ratio)
            left = 0
            upper = (image.height - new_height) // 2
        right = left + new_width
        lower = upper + new_height
        image = image.crop((left, upper, right, lower))

        # Resize the image to the desired size.
        image = image.resize(size, resample=Image.Resampling.BICUBIC)

        # Save the image to a byte stream.
        image_bytes = io.BytesIO()
        image.save(image_bytes, format="PNG", optimize=True, quality=settings.artifact.quality)
        image_bytes.seek(0)
        return image_bytes

    async def _upload_cropped_image(self, image: Image.Image, artifact: Artifact, size: ArtifactSize) -> None:
        image_bytes = await self._crop_image(image, SizeMapping[size])
        filename = get_artifact_name(artifact=artifact, size=size)
        await self._upload_to_s3(image_bytes, artifact.name, filename, "image/png")

    async def _upload_image(
        self,
        name: str,
        file: UploadFile | Image.Image,
        listing: Listing,
        description: str | None = None,
    ) -> Artifact:
        existing_images = await self.get_listing_artifacts(listing.id)
        is_first_image = not any(a.artifact_type == "image" for a in existing_images)

        artifact = Artifact.create(
            user_id=listing.user_id,
            listing_id=listing.id,
            name=name,
            artifact_type="image",
            sizes=list(SizeMapping.keys()),
            description=description,
            is_main=is_first_image,
        )

        image = file if isinstance(file, Image.Image) else Image.open(io.BytesIO(await file.read()))

        await asyncio.gather(
            *(self._upload_cropped_image(image=image, artifact=artifact, size=size) for size in SizeMapping.keys()),
            self._add_item(artifact),
        )
        return artifact

    async def get_raw_artifact(self, artifact_id: str) -> Artifact | None:
        return await self._get_item(artifact_id, Artifact)

    async def _upload_mesh(
        self,
        name: str,
        file: UploadFile,
        listing: Listing,
        artifact_type: Literal["stl", "obj", "ply", "dae"],
        description: str | None = None,
    ) -> Artifact:
        # Converts the mesh to a binary STL file.
        file_data = await file.read()

        tmesh = trimesh.load(io.BytesIO(file_data), file_type=artifact_type)
        if not isinstance(tmesh, trimesh.Trimesh):
            raise BadArtifactError(f"Invalid mesh file: {name} ({type(tmesh)})")

        out_file = io.BytesIO()
        tmesh.export(out_file, file_type="stl")
        out_file.seek(0)

        # Replaces name suffix.
        name = f"{name.rsplit('.', 1)[0]}.stl"

        # Saves the artifact to S3.
        artifact = await self._upload_and_store(name, out_file, listing, "stl", description)

        # Closes the file handlers when done.
        out_file.close()

        return artifact

    async def _upload_xml(
        self,
        name: str,
        file: UploadFile,
        listing: Listing,
        artifact_type: Literal["urdf", "mjcf"],
        description: str | None = None,
    ) -> Artifact:
        # Standardizes the XML file.
        try:
            tree = ET.parse(io.BytesIO(await file.read()))
        except Exception:
            raise BadArtifactError("Invalid XML file")

        # Converts to byte stream.
        out_file = io.BytesIO()
        save_xml(out_file, tree)
        out_file.seek(0)

        # Saves the artifact to S3.
        return await self._upload_and_store(name, out_file, listing, artifact_type, description)

    async def _upload_archive(
        self,
        name: str,
        file: UploadFile,
        listing: Listing,
        artifact_type: Literal["tgz", "zip"],
        description: str | None = None,
    ) -> Artifact:
        with tempfile.TemporaryDirectory() as temp_dir:
            out_file = Path(temp_dir) / name
            with tarfile.open(out_file, mode="w:gz") as archive:
                async for data, subname in self.iter_archive(file, artifact_type):
                    subtype = Path(subname).suffix.lower()
                    temp_path = Path(temp_dir) / subname
                    temp_path.parent.mkdir(parents=True, exist_ok=True)
                    match subtype:
                        case ".stl" | ".obj" | ".ply" | ".dae":
                            tmesh = trimesh.load(io.BytesIO(data), file_type=subtype)
                            if not isinstance(tmesh, trimesh.Trimesh):
                                raise BadArtifactError(f"Invalid mesh file: {subname}")
                            tmesh.export(temp_path, file_type=subtype.lstrip("."))
                            archive.add(temp_path, arcname=subname)

                        case ".png" | ".jpg" | ".jpeg" | ".gif" | ".bmp" | ".tiff" | ".webp":
                            image = Image.open(io.BytesIO(data))
                            match subtype:
                                case ".png":
                                    format = "PNG"
                                case ".jpg" | ".jpeg":
                                    format = "JPEG"
                                case ".gif":
                                    format = "GIF"
                                case ".bmp":
                                    format = "BMP"
                                case ".tiff":
                                    format = "TIFF"
                                case ".webp":
                                    format = "WEBP"
                            image.save(temp_path, format=format)
                            archive.add(temp_path, arcname=subname)

                        case ".urdf" | ".mjcf":
                            try:
                                tree = ET.parse(io.BytesIO(data))
                            except Exception:
                                raise BadArtifactError("Invalid XML file")
                            save_xml(temp_path, tree)
                            archive.add(temp_path, arcname=subname)

                        case _:
                            raise BadArtifactError(f"Invalid file in archive: {subname}")

            logger.info("Created archive: %s", out_file)
            with open(out_file, "rb") as f:
                return await self._upload_and_store(name, f, listing, "tgz", description)

    async def _upload_and_store(
        self,
        name: str,
        file: IO[bytes],
        listing: Listing,
        artifact_type: ArtifactType,
        description: str | None = None,
    ) -> Artifact:
        artifact = Artifact.create(
            user_id=listing.user_id,
            listing_id=listing.id,
            name=name,
            artifact_type=artifact_type,
            description=description,
        )

        # Prepend the artifact ID to the filename
        s3_filename = get_artifact_name(artifact=artifact, name=name, artifact_type=artifact_type)

        await asyncio.gather(
            self._upload_to_s3(
                data=file,
                name=name,
                filename=s3_filename,
                content_type=DOWNLOAD_CONTENT_TYPE[artifact_type],
            ),
            self._add_item(artifact),
        )
        return artifact

    async def upload_artifact(
        self,
        name: str,
        file: UploadFile,
        listing: Listing,
        artifact_type: ArtifactType,
        description: str | None = None,
    ) -> Artifact:
        match artifact_type:
            case "image":
                return await self._upload_image(name, file, listing, description)
            case "stl" | "obj" | "ply" | "dae":
                return await self._upload_mesh(name, file, listing, artifact_type, description)
            case "urdf" | "mjcf":
                return await self._upload_xml(name, file, listing, artifact_type, description)
            case "tgz" | "zip":
                return await self._upload_archive(name, file, listing, artifact_type, description)
            case _:
                raise BadArtifactError(f"Invalid artifact type: {artifact_type}")

    async def _remove_image(self, artifact: Artifact) -> None:
        await asyncio.gather(
            *(self._delete_from_s3(get_artifact_name(artifact=artifact, size=size)) for size in SizeMapping.keys()),
            self._delete_item(artifact),
        )

    async def _remove_raw_artifact(self, artifact: Artifact) -> None:
        await asyncio.gather(
            self._delete_from_s3(get_artifact_name(artifact=artifact)),
            self._delete_item(artifact),
        )

    async def remove_artifact(self, artifact: Artifact) -> None:
        if artifact.artifact_type == "image":
            await self._remove_image(artifact)
        else:
            await self._remove_raw_artifact(artifact)

    async def get_listing_artifacts(
        self,
        listing_id: str,
        additional_filter_expression: ComparisonCondition | None = None,
    ) -> list[Artifact]:
        artifacts = await self._get_items_from_secondary_index(
            "listing_id",
            listing_id,
            Artifact,
            additional_filter_expression=additional_filter_expression,
        )
        return sorted(artifacts, key=lambda a: a.timestamp)

    async def get_listings_artifacts(self, listing_ids: list[str]) -> list[list[Artifact]]:
        artifact_chunks = await self._get_items_from_secondary_index_batch("listing_id", listing_ids, Artifact)
        return [sorted(artifacts, key=lambda a: a.timestamp) for artifacts in artifact_chunks]

    async def edit_artifact(
        self,
        artifact_id: str,
        name: str | None = None,
        description: str | None = None,
    ) -> None:
        artifact = await self.get_raw_artifact(artifact_id)
        if artifact is None:
            raise ItemNotFoundError("Artifact not found")
        artifact_updates: dict[str, Any] = {}  # noqa: ANN401
        if name is not None:
            artifact_updates["name"] = name
        if description is not None:
            artifact_updates["description"] = description
        if artifact_updates:
            await self._update_item(artifact_id, Artifact, artifact_updates)

    async def set_main_image(self, listing_id: str, artifact_id: str) -> None:
        artifacts = await self.get_listing_artifacts(listing_id)
        for artifact in artifacts:
            if artifact.is_main:
                await self._update_item(artifact.id, Artifact, {"is_main": False})

        await self._update_item(artifact_id, Artifact, {"is_main": True})


artifacts_crud = ArtifactsCrud()
