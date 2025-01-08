"""Defines the CRUD operations for the robot-class table."""

import asyncio

from www.crud.base.db import DBCrud, TableKey


class RobotClassCrud(DBCrud):
    """Defines the table holding information about classes of robots."""

    def _get_table_name(self) -> str:
        return "robot-class"

    @classmethod
    def get_keys(cls) -> list[TableKey]:
        return [("id", "S", "HASH")]

    @classmethod
    def get_gsis(cls) -> set[str]:
        return {"user_id"}


robot_class_crud = RobotClassCrud()

if __name__ == "__main__":
    # python -m www.crud.robot_class
    asyncio.run(robot_class_crud.create_table())
