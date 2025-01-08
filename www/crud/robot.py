"""Defines the CRUD operations for the robot table."""

import asyncio

from www.crud.base.db import DBCrud, TableKey


class RobotCrud(DBCrud):
    """Defines the table holding information about individual robots."""

    def _get_table_name(self) -> str:
        return "robot"

    @classmethod
    def get_keys(cls) -> list[TableKey]:
        return [("id", "S", "HASH")]

    @classmethod
    def get_gsis(cls) -> set[str]:
        return {"user_id", "robot_class_id"}


robot_crud = RobotCrud()

if __name__ == "__main__":
    # python -m www.crud.robot
    asyncio.run(robot_crud.create_table())
