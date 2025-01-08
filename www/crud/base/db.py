"""Defines a base CRUD interface for interacting with DynamoDB."""

import asyncio
import functools
import logging
from abc import ABC, abstractmethod
from typing import (
    Any,
    AsyncContextManager,
    AsyncGenerator,
    Literal,
    Self,
    TypeVar,
)

import aioboto3
from pydantic import BaseModel
from types_aiobotocore_dynamodb.service_resource import DynamoDBServiceResource, Table

from www.auth import User
from www.settings import env

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

DEFAULT_CHUNK_SIZE = 100
DEFAULT_SCAN_LIMIT = 1000
ITEMS_PER_PAGE = 12

TableKey = tuple[str, Literal["S", "N", "B"], Literal["HASH", "RANGE"]]
GlobalSecondaryIndex = tuple[str, str, Literal["S", "N", "B"], Literal["HASH", "RANGE"]]


class DBCrud(AsyncContextManager["DBCrud"], ABC):
    def __init__(self) -> None:
        super().__init__()

        self.__db: DynamoDBServiceResource | None = None

    @abstractmethod
    def _get_table_name(self) -> str:
        """Returns the name of the table."""

    @abstractmethod
    def delete_user_data(self, user: User) -> None:
        """Deletes all data for a user."""

    @property
    def db(self) -> DynamoDBServiceResource:
        if self.__db is None:
            raise RuntimeError("Must call __aenter__ first!")
        return self.__db

    @functools.cached_property
    def table_name(self) -> str:
        return f"www-{self._get_table_name()}{env.aws.dynamodb.table_suffix}"

    @property
    async def table(self) -> Table:
        return await self.db.Table(self.table_name)

    @classmethod
    def get_keys(cls) -> list[TableKey]:
        return [("id", "S", "HASH")]

    @classmethod
    def get_gsis(cls) -> set[str]:
        return set()

    @classmethod
    def get_gsi_index_name(cls, colname: str) -> str:
        return f"{colname}_index"

    async def __aenter__(self) -> Self:
        await super().__aenter__()
        session = aioboto3.Session()
        db = session.resource("dynamodb")
        self.__db = await db.__aenter__()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:  # noqa: ANN401
        to_close = []
        if self.__db is not None:
            to_close.append(self.__db)
        await asyncio.gather(
            super().__aexit__(exc_type, exc_val, exc_tb),
            *(resource.__aexit__(exc_type, exc_val, exc_tb) for resource in to_close),
        )

    async def __call__(self) -> AsyncGenerator[Self, None]:
        async with self as crud:
            yield crud

    async def _get_by_known_id(self, record_id: str) -> dict[str, Any] | None:
        table = await self.table
        response = await table.get_item(Key={"id": record_id})
        return response.get("Item")
