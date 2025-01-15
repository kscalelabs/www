"""Defines the CRUD operations for the robot table."""

import asyncio
import re

from boto3.dynamodb.conditions import Key
from pydantic import BaseModel

from www.crud.base.db import DBCrud, TableKey
from www.errors import InvalidNameError
from www.utils.db import new_uuid


class Robot(BaseModel):
    """Defines the data structure for a robot."""

    id: str
    robot_name: str
    description: str
    user_id: str
    class_id: str


class RobotCrud(DBCrud):
    """Defines the table holding information about individual robots."""

    def _get_table_name(self) -> str:
        return "robot"

    @classmethod
    def get_keys(cls) -> list[TableKey]:
        return [("id", "S", "HASH")]

    @classmethod
    def get_gsis(cls) -> set[str]:
        return {"robot_name", "user_id", "class_id"}

    def _is_valid_name(self, robot_name: str) -> bool:
        return len(robot_name) >= 3 and len(robot_name) < 64 and re.match(r"^[a-zA-Z0-9_-]+$", robot_name) is not None

    def _is_valid_description(self, description: str | None) -> bool:
        return description is None or len(description) < 2048

    async def add_robot(
        self,
        robot_name: str,
        user_id: str,
        class_id: str,
        description: str | None = None,
    ) -> Robot:
        """Adds a robot to the database.

        Args:
            robot_name: The name of the robot.
            user_id: The ID of the user who owns the robot.
            class_id: The ID of the robot class that the robot belongs to.
            description: The description of the robot.

        Returns:
            The robot that was added.
        """
        if not self._is_valid_name(robot_name):
            raise InvalidNameError(f"Invalid robot name: {robot_name}")
        if not self._is_valid_description(description):
            raise InvalidNameError("Invalid robot description")

        robot_id = new_uuid()

        robot = Robot(
            id=robot_id,
            robot_name=robot_name,
            description="Empty description" if description is None else description,
            user_id=user_id,
            class_id=class_id,
        )

        # Check if the robot already exists.
        existing_robot = await self.get_robot_by_name(robot_name, user_id)
        if existing_robot is not None:
            raise ValueError(f"Robot with name '{robot_name}' already exists")

        table = await self.table
        try:
            await table.put_item(
                Item=robot.model_dump(),
                ConditionExpression="attribute_not_exists(robot_name)",
            )
        except table.meta.client.exceptions.ConditionalCheckFailedException:
            raise ValueError(f"Robot with name '{robot_name}' already exists")

        return robot

    async def update_robot(
        self,
        robot: Robot,
        user_id: str,
        new_robot_name: str | None = None,
        new_description: str | None = None,
    ) -> Robot:
        """Updates a robot in the database.

        Args:
            robot: The robot to update.
            user_id: The ID of the user who owns the robot.
            new_robot_name: The new name of the robot.
            new_description: The new description of the robot.

        Returns:
            The robot that was updated.
        """
        if new_robot_name is not None and not self._is_valid_name(new_robot_name):
            raise InvalidNameError(f"Invalid robot name: {new_robot_name}")
        if new_description is not None and not self._is_valid_description(new_description):
            raise InvalidNameError("Invalid robot description")

        table = await self.table

        # Populates values.
        old_robot_name = robot.robot_name
        if new_robot_name is not None:
            if old_robot_name != new_robot_name:
                if (await self.get_robot_by_name(new_robot_name, user_id)) is not None:
                    raise ValueError(f"Robot with name '{new_robot_name}' already exists")
            robot.robot_name = new_robot_name

        if new_description is not None:
            robot.description = new_description

        try:
            await table.update_item(
                Key={"id": robot.id},
                UpdateExpression="SET robot_name = :new_robot_name, description = :new_description",
                ConditionExpression="attribute_not_exists(robot_name) OR robot_name = :old_robot_name",
                ExpressionAttributeValues={
                    ":new_robot_name": robot.robot_name,
                    ":new_description": robot.description,
                    ":old_robot_name": old_robot_name,
                },
            )
        except table.meta.client.exceptions.ConditionalCheckFailedException:
            raise ValueError(f"Robot with name '{new_robot_name}' already exists")

        return robot

    async def delete_robot(self, robot: Robot) -> None:
        """Deletes a robot from the database."""
        table = await self.table
        await table.delete_item(Key={"id": robot.id})

    async def get_robot_by_name(self, robot_name: str, user_id: str) -> Robot | None:
        """Gets a robot by name."""
        table = await self.table
        response = await table.query(
            IndexName=self.get_gsi_index_name("robot_name"),
            KeyConditionExpression=Key("robot_name").eq(robot_name) & Key("user_id").eq(user_id),
        )
        if (items := response.get("Items", [])) == []:
            return None
        if len(items) > 1:
            raise ValueError(f"Multiple robots with name '{robot_name}' found")
        return Robot.model_validate(items[0])

    async def get_robot_by_id(self, id: str, user_id: str) -> Robot | None:
        """Gets a robot by ID."""
        table = await self.table
        response = await table.query(
            IndexName=self.get_gsi_index_name("user_id"),
            KeyConditionExpression=Key("user_id").eq(user_id),
            FilterExpression=Key("id").eq(id),
        )
        if (items := response.get("Items", [])) == []:
            return None
        if len(items) > 1:
            raise ValueError(f"Multiple robots with ID '{id}' found")
        return Robot.model_validate(items[0])

    async def list_robots(self, user_id: str | None = None) -> list[Robot]:
        """Gets all robots."""
        table = await self.table
        if user_id is not None:
            response = await table.query(
                IndexName=self.get_gsi_index_name("user_id"),
                KeyConditionExpression=Key("user_id").eq(user_id),
            )
        else:
            response = await table.scan()
        return [Robot.model_validate(item) for item in response.get("Items", [])]


robot_crud = RobotCrud()

if __name__ == "__main__":
    # python -m www.crud.robot
    asyncio.run(robot_crud.create_table())
