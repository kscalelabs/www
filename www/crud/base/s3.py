"""Defines a base CRUD interface for interacting with S3 buckets."""

import asyncio
import functools
import logging
from abc import ABC, abstractmethod
from typing import (
    IO,
    Any,
    AsyncContextManager,
    AsyncGenerator,
    Self,
)

import aioboto3
from aiobotocore.response import StreamingBody
from botocore.exceptions import ClientError
from types_aiobotocore_s3.service_resource import Bucket, S3ServiceResource

from www.settings import settings

logger = logging.getLogger(__name__)


class BaseS3Crud(AsyncContextManager["BaseS3Crud"], ABC):
    def __init__(self) -> None:
        super().__init__()
        self.__s3: S3ServiceResource | None = None

    @abstractmethod
    def _get_directory(self) -> str:
        """Returns the name of the directory."""

    @property
    def s3(self) -> S3ServiceResource:
        if self.__s3 is None:
            raise RuntimeError("Must call __aenter__ first!")
        return self.__s3

    @property
    def bucket(self) -> Bucket:
        return self.s3.Bucket(settings.s3.bucket)

    @functools.cached_property
    def prefix(self) -> str:
        return f"{settings.s3.prefix}{self._get_directory()}/"

    async def __aenter__(self) -> Self:
        session = aioboto3.Session()
        s3 = session.resource("s3")
        _, s3 = await asyncio.gather(super().__aenter__(), s3.__aenter__())
        self.__s3 = s3
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:  # noqa: ANN401
        to_close = []
        if self.__s3 is not None:
            to_close.append(self.__s3)
        await asyncio.gather(
            super().__aexit__(exc_type, exc_val, exc_tb),
            *(resource.__aexit__(exc_type, exc_val, exc_tb) for resource in to_close),
        )

    async def upload_to_s3(self, data: IO[bytes], name: str, filename: str, content_type: str) -> None:
        """Uploads some data to S3."""
        try:
            bucket = await self.s3.Bucket(settings.s3.bucket)

            sanitized_name = name.replace("\u202f", " ").replace("\xa0", " ")

            await bucket.put_object(
                Key=f"{self.prefix}{filename}",
                Body=data,
                ContentType=content_type,
                ContentDisposition=f'attachment; filename="{sanitized_name}"',
            )
            logger.info("S3 upload successful")
        except ClientError as e:
            logger.exception("S3 upload failed: %s", e)
            raise

    async def download_from_s3(self, filename: str) -> StreamingBody:
        """Downloads an object from S3.

        Args:
            filename: The filename of the object to download.

        Returns:
            The object data.
        """
        bucket = await self.s3.Bucket(settings.s3.bucket)
        obj = await bucket.Object(f"{self.prefix}{filename}")
        data = await obj.get()
        return data["Body"]

    async def delete_from_s3(self, filename: str) -> None:
        """Deletes an object from S3.

        Args:
            filename: The filename of the object to delete.
        """
        bucket = await self.s3.Bucket(settings.s3.bucket)
        await bucket.delete_objects(Delete={"Objects": [{"Key": f"{self.prefix}{filename}"}]})

    async def create_s3_bucket(self) -> None:
        """Creates an S3 bucket if it does not already exist."""
        try:
            await self.s3.meta.client.head_bucket(Bucket=settings.s3.bucket)
            logger.info("Found existing bucket %s", settings.s3.bucket)
        except ClientError:
            logger.info("Creating %s bucket", settings.s3.bucket)
            await self.s3.create_bucket(Bucket=settings.s3.bucket)

            logger.info("Updating %s CORS configuration", settings.s3.bucket)
            s3_cors = await self.s3.BucketCors(settings.s3.bucket)
            await s3_cors.put(
                CORSConfiguration={
                    "CORSRules": [
                        {
                            "AllowedHeaders": ["*"],
                            "AllowedMethods": ["GET"],
                            "AllowedOrigins": ["*"],
                            "ExposeHeaders": ["ETag"],
                        }
                    ]
                },
            )

    async def generate_presigned_upload_url(
        self,
        filename: str,
        s3_key: str,
        content_type: str,
        checksum_algorithm: str = "SHA256",
        expires_in: int = 3600,
    ) -> str:
        """Generates a presigned URL for uploading a file to S3.

        Args:
            filename: Original filename for Content-Disposition
            s3_key: The S3 key where the file will be stored
            content_type: The content type of the file
            checksum_algorithm: Algorithm used for upload integrity verification (SHA256, SHA1, CRC32)
            expires_in: Number of seconds until URL expires

        Returns:
            Presigned URL for uploading
        """
        try:
            return await self.s3.meta.client.generate_presigned_url(
                ClientMethod="put_object",
                Params={
                    "Bucket": settings.s3.bucket,
                    "Key": f"{self.prefix}{s3_key}",
                    "ContentType": content_type,
                    "ContentDisposition": f'attachment; filename="{filename}"',
                    "ChecksumAlgorithm": checksum_algorithm,
                },
                ExpiresIn=expires_in,
            )
        except ClientError as e:
            logger.error("Failed to generate presigned URL: %s", e)
            raise

    async def delete_s3_bucket(self) -> None:
        """Deletes an S3 bucket."""
        bucket = await self.s3.Bucket(settings.s3.bucket)
        logger.info("Deleting bucket %s", settings.s3.bucket)
        async for obj in bucket.objects.all():
            await obj.delete()
        await bucket.delete()

    async def __call__(self) -> AsyncGenerator[Self, None]:
        async with self as crud:
            yield crud

    @classmethod
    async def get(cls) -> AsyncGenerator[Self, None]:
        async with cls() as crud:
            yield crud
