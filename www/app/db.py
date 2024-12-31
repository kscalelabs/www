"""Defines base tools for interacting with the database."""

import argparse
import asyncio
import logging
from typing import AsyncGenerator, Literal, Self

from www.app.crud.artifacts import ArtifactsCrud
from www.app.crud.base import TABLE_NAME, BaseCrud
from www.app.crud.krecs import KRecsCrud
from www.app.crud.listings import ListingsCrud
from www.app.crud.onshape import OnshapeCrud
from www.app.crud.robots import RobotsCrud
from www.app.crud.users import UserCrud


class Crud(
    OnshapeCrud,
    UserCrud,
    ListingsCrud,
    ArtifactsCrud,
    KRecsCrud,
    RobotsCrud,
    BaseCrud,
):
    """Composes the various CRUD classes into a single class."""

    @classmethod
    async def get(cls) -> AsyncGenerator[Self, None]:
        async with cls() as crud:
            yield crud


async def create_tables(crud: Crud | None = None, deletion_protection: bool = False) -> None:
    """Initializes all of the database tables.

    Args:
        crud: The top-level CRUD class.
        deletion_protection: Whether to enable deletion protection on the tables.
    """
    logging.basicConfig(level=logging.INFO)

    if crud is None:
        async with Crud() as new_crud:
            await create_tables(new_crud)

    else:
        gsis_set = crud.get_gsis()
        gsis: list[tuple[str, str, Literal["S", "N", "B"], Literal["HASH", "RANGE"]]] = [
            (Crud.get_gsi_index_name(g), g, "S", "HASH") for g in gsis_set
        ]

        await asyncio.gather(
            crud._create_dynamodb_table(
                name=TABLE_NAME,
                keys=[
                    ("id", "S", "HASH"),
                ],
                gsis=gsis,
                deletion_protection=deletion_protection,
            ),
            crud._create_s3_bucket(),
        )


async def delete_tables(crud: Crud | None = None) -> None:
    """Deletes all of the database tables.

    Args:
        crud: The top-level CRUD class.
    """
    logging.basicConfig(level=logging.INFO)

    if crud is None:
        async with Crud() as new_crud:
            await delete_tables(new_crud)

    else:
        await crud._delete_dynamodb_table(TABLE_NAME)
        await crud._delete_s3_bucket()


async def populate_with_dummy_data(crud: Crud | None = None) -> None:
    """Populates the database with dummy data.

    Args:
        crud: The top-level CRUD class.
    """
    if crud is None:
        async with Crud() as new_crud:
            await populate_with_dummy_data(new_crud)

    else:
        raise NotImplementedError("This function is not yet implemented.")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["create", "delete", "populate"])
    args = parser.parse_args()

    async with Crud() as crud:
        match args.action:
            case "create":
                await create_tables(crud)
            case "delete":
                await delete_tables(crud)
            case "populate":
                await populate_with_dummy_data(crud)
            case _:
                raise ValueError(f"Invalid action: {args.action}")


if __name__ == "__main__":
    # python -m store.app.db
    asyncio.run(main())
