"""Defines an endpoint for managing types of robots.

Robots need to access metadata about each robot in order to
"""

from www.crud.base.db import BaseDbCrud


class RobotTypeCrud(BaseDbCrud):
    def _get_table_name(self) -> str:
        return "robot_type"
