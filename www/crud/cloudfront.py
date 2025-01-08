"""Defines a base CRUD interface for interacting with Cloudfront."""

import asyncio
import logging
from typing import (
    Any,
    AsyncContextManager,
    Self,
)

import aioboto3
from types_aiobotocore_cloudfront.client import CloudFrontClient
from types_aiobotocore_cloudfront.type_defs import CreateDistributionResultTypeDef

from www.settings import env

logger = logging.getLogger(__name__)


class CloudFrontCrud(AsyncContextManager["CloudFrontCrud"]):
    def __init__(self) -> None:
        super().__init__()
        self.__cf: CloudFrontClient | None = None

    @property
    def cf(self) -> CloudFrontClient:
        if self.__cf is None:
            raise RuntimeError("Must call __aenter__ first!")
        return self.__cf

    async def __aenter__(self) -> Self:
        await super().__aenter__()
        session = aioboto3.Session()
        cf = session.client("cloudfront")
        self.__cf = await cf.__aenter__()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:  # noqa: ANN401
        to_close = []
        if self.__cf is not None:
            to_close.append(self.__cf)
        await asyncio.gather(
            super().__aexit__(exc_type, exc_val, exc_tb),
            *(resource.__aexit__(exc_type, exc_val, exc_tb) for resource in to_close),
        )

    async def create_distribution(self) -> CreateDistributionResultTypeDef:
        return await self.cf.create_distribution(
            DistributionConfig={
                "CallerReference": "api.kscale.dev",
                "Origins": {
                    "Items": [
                        {
                            "Id": "MyOrigin",
                            "DomainName": f"{env.aws.s3.bucket}.s3.amazonaws.com",
                            "S3OriginConfig": {
                                "OriginAccessIdentity": "",
                            },
                        }
                    ],
                    "Quantity": 1,
                },
                "DefaultCacheBehavior": {
                    "TargetOriginId": "MyOrigin",
                    "ViewerProtocolPolicy": "allow-all",
                    "AllowedMethods": {
                        "Quantity": 2,
                        "Items": ["GET", "HEAD"],
                    },
                    "DefaultTTL": 3600,
                    "MaxTTL": 86400,
                    "MinTTL": 0,
                    "ForwardedValues": {
                        "QueryString": False,
                        "Cookies": {"Forward": "none"},
                    },
                },
                "Comment": "CloudFront distribution for LocalStack S3 bucket",
                "Enabled": True,
            },
        )


cf_crud = CloudFrontCrud()


async def create_cloudfront_distribution() -> None:
    async with cf_crud as crud:
        await crud.create_distribution()


if __name__ == "__main__":
    # python -m www.crud.cloudfront
    asyncio.run(create_cloudfront_distribution())
