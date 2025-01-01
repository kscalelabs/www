"""Defines base tools for interacting with the database."""

import argparse
import asyncio

import colorlogging

from www.crud.base import BaseDbCrud, BaseS3Crud
from www.crud.robots import RobotsCrud

Crud = BaseDbCrud | BaseS3Crud

CRUDS: list[Crud] = [
    RobotsCrud(),
]


async def create_tables() -> None:
    """Creates all the tables and S3 buckets."""

    async def _create(crud: Crud) -> None:
        async with crud:

            async def _create_s3_bucket(crud: Crud) -> None:
                if isinstance(crud, BaseS3Crud):
                    await crud.create_s3_bucket()

            async def _create_dynamodb_table(crud: Crud) -> None:
                if isinstance(crud, BaseDbCrud):
                    await crud.create_dynamodb_table()

            await asyncio.gather(_create_s3_bucket(crud), _create_dynamodb_table(crud))

    await asyncio.gather(*(_create(crud) for crud in CRUDS))


async def delete_tables() -> None:
    """Deletes all the tables and S3 buckets."""

    async def _delete(crud: Crud) -> None:
        async with crud:

            async def _delete_s3_bucket(crud: Crud) -> None:
                if isinstance(crud, BaseS3Crud):
                    await crud.delete_s3_bucket()

            async def _delete_dynamodb_table(crud: Crud) -> None:
                if isinstance(crud, BaseDbCrud):
                    await crud.delete_dynamodb_table()

            await asyncio.gather(_delete_s3_bucket(crud), _delete_dynamodb_table(crud))

    await asyncio.gather(*(_delete(crud) for crud in CRUDS))


async def main() -> None:
    colorlogging.configure()

    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["create", "delete", "populate"])
    args = parser.parse_args()

    match args.action:
        case "create":
            await create_tables()
        case "delete":
            await delete_tables()
        case _:
            raise ValueError(f"Invalid action: {args.action}")


if __name__ == "__main__":
    # python -m www.db
    asyncio.run(main())
