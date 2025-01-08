"""Defines the common CRUD operations for the application."""

__all__ = ["robot_crud", "robot_class_crud", "s3_crud"]

import asyncio
import logging

from .base.s3 import s3_crud
from .robot import robot_crud
from .robot_class import robot_class_crud

logger = logging.getLogger(__name__)


async def create_s3_bucket() -> None:
    logger.info("Creating S3 bucket...")
    async with s3_crud as s3:
        await s3.create_bucket()


async def create_robot_table() -> None:
    logger.info("Creating robot table...")
    async with robot_crud as robot:
        await robot.create_table()


async def create_robot_class_table() -> None:
    logger.info("Creating robot class table...")
    async with robot_class_crud as robot_class:
        await robot_class.create_table()


async def create() -> None:
    await asyncio.gather(
        create_s3_bucket(),
        create_robot_table(),
        create_robot_class_table(),
    )
