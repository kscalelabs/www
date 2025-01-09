"""Defines the API endpoint for managing robot classes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from www.auth import User, require_permissions, require_user
from www.crud.robot_class import RobotClass, RobotClassCrud, robot_class_crud
from www.errors import ActionNotAllowedError, ItemNotFoundError

router = APIRouter()


@router.get("/")
async def get_robot_classes(
    crud: RobotClassCrud = Depends(robot_class_crud),
) -> list[RobotClass]:
    """Gets all robot classes."""
    return await crud.list_robot_classes()


@router.get("/name/{class_name}")
async def get_robot_class_by_name(
    class_name: str,
    crud: RobotClassCrud = Depends(robot_class_crud),
) -> RobotClass:
    """Gets a robot class by name."""
    robot_class = await crud.get_robot_class_by_name(class_name)
    if robot_class is None:
        raise ItemNotFoundError(f"Robot class '{class_name}' not found")
    return robot_class


@router.get("/user/{user_id}")
async def get_robot_classes_for_user(
    user_id: str,
    user: Annotated[User, Depends(require_user)],
    crud: RobotClassCrud = Depends(robot_class_crud),
) -> list[RobotClass]:
    """Gets a robot class."""
    if user_id.lower() == "me":
        return await crud.list_robot_classes(user.id)
    else:
        return await crud.list_robot_classes(user_id)


@router.put("/add")
async def add_robot_class(
    class_name: str,
    user: Annotated[User, Depends(require_permissions({"upload"}))],
    crud: RobotClassCrud = Depends(robot_class_crud),
) -> RobotClass:
    """Adds a robot class."""
    return await crud.add_robot_class(class_name, user.id)


@router.put("/update")
async def update_robot_class(
    class_name: str,
    user: Annotated[User, Depends(require_permissions({"upload"}))],
    crud: RobotClassCrud = Depends(robot_class_crud),
    new_class_name: str | None = Query(
        default=None,
        description="The new name of the robot class",
    ),
    new_description: str | None = Query(
        default=None,
        description="The new description of the robot class",
    ),
) -> RobotClass:
    """Updates a robot class."""
    # Get the existing robot class by name.
    existing_robot_class = await crud.get_robot_class_by_name(class_name)
    if existing_robot_class is None:
        raise ItemNotFoundError(class_name)
    if existing_robot_class.user_id != user.id:
        raise ActionNotAllowedError("You are not the owner of this robot class")

    return await crud.update_robot_class(
        robot_class=existing_robot_class,
        new_class_name=new_class_name,
        new_description=new_description,
    )


@router.delete("/delete")
async def delete_robot_class(
    class_name: str,
    user: Annotated[User, Depends(require_user)],
    crud: RobotClassCrud = Depends(robot_class_crud),
) -> bool:
    """Deletes a robot class."""
    robot_class = await crud.get_robot_class_by_name(class_name)
    if robot_class is None:
        raise ItemNotFoundError(f"Robot class '{class_name}' not found")
    if robot_class.user_id != user.id:
        raise ActionNotAllowedError("You are not the owner of this robot class")
    await crud.delete_robot_class(robot_class)
    return True
