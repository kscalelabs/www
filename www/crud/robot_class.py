"""Defines the CRUD operations for the robot-class table."""

import asyncio
import re

from boto3.dynamodb.conditions import Key
from pydantic import BaseModel

from www.crud.base.db import DBCrud, TableKey
from www.errors import InvalidNameError
from www.utils.db import new_uuid


class RobotClass(BaseModel):
    """Defines the data structure for a robot class."""

    id: str
    class_name: str
    description: str
    user_id: str


class RobotClassCrud(DBCrud):
    """Defines the table holding information about classes of robots."""

    def _get_table_name(self) -> str:
        return "robot-class"

    @classmethod
    def get_keys(cls) -> list[TableKey]:
        return [("id", "S", "HASH")]

    @classmethod
    def get_gsis(cls) -> set[str]:
        return {"class_name", "user_id"}

    def _is_valid_name(self, class_name: str) -> bool:
        return len(class_name) >= 3 and len(class_name) < 64 and re.match(r"^[a-zA-Z0-9_-]+$", class_name) is not None

    def _is_valid_description(self, description: str | None) -> bool:
        return description is None or len(description) < 2048

    async def add_robot_class(
        self,
        class_name: str,
        user_id: str,
        description: str | None = None,
    ) -> RobotClass:
        """Adds a robot class to the database.

        Args:
            class_name: The unique robot class name.
            user_id: The ID of the user who owns the robot class.
            description: The description of the robot class.

        Returns:
            The robot class that was added.
        """
        if not self._is_valid_name(class_name):
            raise InvalidNameError(f"Invalid robot class name: {class_name}")
        if not self._is_valid_description(description):
            raise InvalidNameError("Invalid robot class description")

        robot_class_id = new_uuid()

        robot_class = RobotClass(
            id=robot_class_id,
            class_name=class_name,
            description="Empty description" if description is None else description,
            user_id=user_id,
        )

        # Check if the robot class already exists.
        existing_robot_class = await self.get_robot_class_by_name(class_name)
        if existing_robot_class is not None:
            raise ValueError(f"Robot class with name '{class_name}' already exists")

        table = await self.table
        try:
            await table.put_item(
                Item=robot_class.model_dump(),
                ConditionExpression="attribute_not_exists(class_name)",
            )
        except table.meta.client.exceptions.ConditionalCheckFailedException:
            raise ValueError(f"Robot class with name '{class_name}' already exists")

        return robot_class

    async def update_robot_class(
        self,
        robot_class: RobotClass,
        new_class_name: str | None = None,
        new_description: str | None = None,
    ) -> RobotClass:
        """Updates a robot class in the database.

        Args:
            robot_class: The robot class to update.
            new_class_name: The new name of the robot class.
            new_description: The new description of the robot class.

        Returns:
            The robot class that was updated.
        """
        if new_class_name is not None and not self._is_valid_name(new_class_name):
            raise InvalidNameError(f"Invalid robot class name: {new_class_name}")
        if new_description is not None and not self._is_valid_description(new_description):
            raise InvalidNameError("Invalid robot class description")

        table = await self.table

        # Populates values.
        old_class_name = robot_class.class_name
        if new_class_name is not None:
            if old_class_name != new_class_name:
                if (await self.get_robot_class_by_name(new_class_name)) is not None:
                    raise ValueError(f"Robot class with name '{new_class_name}' already exists")
            robot_class.class_name = new_class_name

        if new_description is not None:
            robot_class.description = new_description

        try:
            await table.update_item(
                Key={"id": robot_class.id},
                UpdateExpression=("SET class_name = :new_class_name, description = :new_description"),
                ConditionExpression="attribute_not_exists(class_name) OR class_name = :old_class_name",
                ExpressionAttributeValues={
                    ":new_class_name": robot_class.class_name,
                    ":new_description": robot_class.description,
                    ":old_class_name": old_class_name,
                },
            )
        except table.meta.client.exceptions.ConditionalCheckFailedException:
            raise ValueError(f"Robot class with name '{new_class_name}' already exists")

        return robot_class

    async def delete_robot_class(self, robot_class: RobotClass) -> None:
        """Deletes a robot class from the database."""
        table = await self.table
        await table.delete_item(Key={"id": robot_class.id})

    async def get_robot_class_by_name(self, class_name: str) -> RobotClass | None:
        """Gets a robot class by name."""
        table = await self.table
        response = await table.query(
            IndexName=self.get_gsi_index_name("class_name"),
            KeyConditionExpression=Key("class_name").eq(class_name),
        )
        if (items := response.get("Items", [])) == []:
            return None
        if len(items) > 1:
            raise ValueError(f"Multiple robot classes with name '{class_name}' found")
        return RobotClass.model_validate(items[0])

    async def get_robot_class_by_id(self, id: str) -> RobotClass | None:
        """Gets a robot class by ID."""
        table = await self.table
        response = await table.get_item(Key={"id": id})
        if (item := response.get("Item")) is None:
            return None
        return RobotClass.model_validate(item)

    async def list_robot_classes(self, user_id: str | None = None) -> list[RobotClass]:
        """Gets all robot classes."""
        table = await self.table
        if user_id is not None:
            response = await table.query(
                IndexName=self.get_gsi_index_name("user_id"),
                KeyConditionExpression=Key("user_id").eq(user_id),
            )
        else:
            response = await table.scan()
        return [RobotClass.model_validate(item) for item in response.get("Items", [])]


robot_class_crud = RobotClassCrud()

if __name__ == "__main__":
    # python -m www.crud.robot_class
    asyncio.run(robot_class_crud.create_table())
