"""Defines the API endpoint for managing robots."""

from typing import Annotated, Self

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from www.auth import User, require_permissions, require_user
from www.crud.robot import Robot, RobotCrud, robot_crud
from www.crud.robot_class import RobotClass, RobotClassCrud, robot_class_crud
from www.errors import ActionNotAllowedError, ItemNotFoundError
from www.routers.robot_class import get_robot_class_by_name

router = APIRouter()


class RobotResponse(BaseModel):
    id: str
    robot_name: str
    description: str
    user_id: str
    class_name: str

    @classmethod
    def from_robot(cls, robot: Robot, robot_class: RobotClass) -> Self:
        return cls(
            id=robot.id,
            robot_name=robot.robot_name,
            description=robot.description,
            user_id=robot.user_id,
            class_name=robot_class.class_name,
        )


@router.get("/")
async def get_robots(
    crud: RobotCrud = Depends(robot_crud),
) -> list[Robot]:
    return await crud.list_robots()


async def _get_robot_and_class_by_id(
    id: str,
    crud: Annotated[RobotCrud, Depends(robot_crud)],
    cls_crud: Annotated[RobotClassCrud, Depends(robot_class_crud)],
) -> tuple[Robot, RobotClass]:
    robot = await crud.get_robot_by_id(id)
    if robot is None:
        raise ItemNotFoundError(f"Robot '{id}' not found")
    robot_class = await cls_crud.get_robot_class_by_id(robot.class_id)
    if robot_class is None:
        raise ItemNotFoundError(f"Robot class '{robot.class_id}' not found")
    return robot, robot_class


async def _get_base_robot_by_name(
    robot_name: str,
    crud: Annotated[RobotCrud, Depends(robot_crud)],
) -> Robot:
    robot = await crud.get_robot_by_name(robot_name)
    if robot is None:
        raise ItemNotFoundError(f"Robot '{robot_name}' not found")
    return robot


async def _get_robot_and_class_by_name(
    robot_name: str,
    crud: Annotated[RobotCrud, Depends(robot_crud)],
    cls_crud: Annotated[RobotClassCrud, Depends(robot_class_crud)],
) -> tuple[Robot, RobotClass]:
    robot = await crud.get_robot_by_name(robot_name)
    if robot is None:
        raise ItemNotFoundError(f"Robot '{robot_name}' not found")
    robot_class = await cls_crud.get_robot_class_by_id(robot.class_id)
    if robot_class is None:
        raise ItemNotFoundError(f"Robot class '{robot.class_id}' not found")
    return robot, robot_class


@router.get("/name/{robot_name}")
async def get_robot_by_name(
    robot_name: str,
    crud: Annotated[RobotCrud, Depends(robot_crud)],
    cls_crud: Annotated[RobotClassCrud, Depends(robot_class_crud)],
) -> RobotResponse:
    robot, robot_class = await _get_robot_and_class_by_name(robot_name, crud, cls_crud)
    return RobotResponse.from_robot(robot, robot_class)


@router.get("/id/{id}")
async def get_robot_by_id(
    id: str,
    crud: Annotated[RobotCrud, Depends(robot_crud)],
    cls_crud: Annotated[RobotClassCrud, Depends(robot_class_crud)],
) -> RobotResponse:
    robot, robot_class = await _get_robot_and_class_by_id(id, crud, cls_crud)
    return RobotResponse.from_robot(robot, robot_class)


@router.get("/user/{user_id}")
async def get_robots_for_user(
    user_id: str,
    user: Annotated[User, Depends(require_user)],
    crud: Annotated[RobotCrud, Depends(robot_crud)],
) -> list[Robot]:
    if user_id.lower() == "me":
        return await crud.list_robots(user.id)
    else:
        return await crud.list_robots(user_id)


@router.put("/{robot_name}")
async def add_robot(
    robot_name: str,
    user: Annotated[User, Depends(require_permissions({"upload"}))],
    robot_class: Annotated[RobotClass, Depends(get_robot_class_by_name)],
    crud: Annotated[RobotCrud, Depends(robot_crud)],
) -> RobotResponse:
    robot = await crud.add_robot(robot_name, user.id, robot_class.id)
    return RobotResponse.from_robot(robot, robot_class)


@router.post("/{robot_name}")
async def update_robot(
    user: Annotated[User, Depends(require_permissions({"upload"}))],
    existing_robot_tuple: Annotated[tuple[Robot, RobotClass], Depends(_get_robot_and_class_by_name)],
    crud: Annotated[RobotCrud, Depends(robot_crud)],
    new_robot_name: str | None = Query(
        default=None,
        description="The new name of the robot",
    ),
    new_description: str | None = Query(
        default=None,
        description="The new description of the robot",
    ),
) -> RobotResponse:
    existing_robot, existing_robot_class = existing_robot_tuple
    if existing_robot.user_id != user.id:
        raise ActionNotAllowedError("You are not the owner of this robot")
    robot = await crud.update_robot(existing_robot, new_robot_name, new_description)
    return RobotResponse.from_robot(robot, existing_robot_class)


@router.delete("/{robot_name}")
async def delete_robot(
    user: Annotated[User, Depends(require_user)],
    robot: Annotated[Robot, Depends(_get_base_robot_by_name)],
    crud: Annotated[RobotCrud, Depends(robot_crud)],
) -> bool:
    if robot.user_id != user.id:
        raise ActionNotAllowedError("You are not the owner of this robot")
    await crud.delete_robot(robot)
    return True
