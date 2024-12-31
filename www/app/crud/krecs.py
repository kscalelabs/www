"""Defines the CRUD interface for handling user-uploaded KRecs."""

import asyncio
import io
import logging
from types import TracebackType
from typing import Self

from fastapi import UploadFile

from www.app.crud.base import TABLE_NAME, BaseDbCrud
from www.app.model import KRec

logger = logging.getLogger(__name__)


class KRecsCrud(BaseDbCrud):
    """CRUD operations for KRecs."""

    def __init__(self) -> None:
        super().__init__()

    async def __aenter__(self) -> Self:
        await super().__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await super().__aexit__(exc_type, exc_val, exc_tb)

    async def create_krec(
        self,
        user_id: str,
        robot_id: str,
        name: str,
        file: UploadFile,
        description: str | None = None,
    ) -> KRec:
        """Create a new KRec and upload its file."""
        krec = KRec.create(user_id=user_id, robot_id=robot_id, name=name, description=description)

        file_data = io.BytesIO(await file.read())

        key = f"krecs/{krec.id}/{name}"
        await asyncio.gather(
            self._upload_to_s3(
                data=file_data,
                name=name,
                filename=key,
                content_type="video/x-matroska",
            ),
            self._add_item(krec),
        )

        return krec

    async def get_krec(self, krec_id: str) -> KRec | None:
        return await self._get_item(krec_id, KRec)

    async def list_krecs(self, robot_id: str) -> list[KRec]:
        """List all krecs for a robot."""
        table = await self.db.Table(TABLE_NAME)
        response = await table.query(
            IndexName=self.get_gsi_index_name("robot_id"),
            KeyConditionExpression="#robot_id = :robot_id",
            ExpressionAttributeNames={
                "#robot_id": "robot_id",
            },
            ExpressionAttributeValues={
                ":robot_id": robot_id,
            },
        )

        return [self._validate_item(item, KRec) for item in response.get("Items", [])]

    async def delete_krec(self, krec_id: str) -> None:
        """Delete a krec."""
        await self._delete_item(krec_id)
