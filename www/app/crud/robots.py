"""This module provides CRUD operations for robots."""

import time
from typing import NotRequired, TypedDict, Unpack

from www.app.crud.base import BaseDbCrud, ItemNotFoundError
from www.app.model import Listing, Robot


class RobotData(TypedDict):
    user_id: str
    listing_id: str
    name: str
    description: NotRequired[str | None]
    updated_at: NotRequired[int]


class RobotsCrud(BaseDbCrud):
    """CRUD operations for Robots."""

    def _get_table_name(self) -> str:
        return "robots"

    @classmethod
    def get_gsis(cls) -> set[str]:
        return super().get_gsis().union({"listing_id"})

    async def create_robot(self, **robot_data: Unpack[RobotData]) -> Robot:
        # Verify listing exists
        listing = await self._get_item(robot_data["listing_id"], Listing)
        if not listing:
            raise ItemNotFoundError(f"Listing with ID {robot_data['listing_id']} not found")

        robot = Robot.create(
            user_id=robot_data["user_id"],
            listing_id=robot_data["listing_id"],
            name=robot_data["name"],
            description=robot_data.get("description"),
        )
        await self._add_item(robot)
        return robot

    async def get_robot(self, robot_id: str) -> Robot:
        robot = await self._get_item(robot_id, Robot)
        if not robot:
            raise ItemNotFoundError("Robot not found")
        return robot

    async def get_robots_by_user_id(self, user_id: str) -> list[Robot]:
        robots = await self._get_items_from_secondary_index("user_id", user_id, Robot)
        return robots

    async def get_robots_by_listing_id(self, listing_id: str) -> list[Robot]:
        robots = await self._get_items_from_secondary_index("listing_id", listing_id, Robot)
        return robots

    async def update_robot(self, robot_id: str, update_data: RobotData) -> Robot:
        robot = await self.get_robot(robot_id)
        if not robot:
            raise ItemNotFoundError("Robot not found")

        update_data["updated_at"] = int(time.time())
        # Convert TypedDict to regular dict
        update_dict = dict(update_data)
        await self._update_item(robot_id, Robot, update_dict)

        updated_robot = await self.get_robot(robot_id)
        return updated_robot

    async def delete_robot(self, robot: Robot) -> None:
        await self._delete_item(robot)


robots_crud = RobotsCrud()
