"""Defines the API endpoint for managing robot classes."""

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from www.auth import User, require_permissions, require_user
from www.crud.base.s3 import S3Crud, s3_crud
from www.crud.robot_class import RobotClass, RobotClassCrud, robot_class_crud
from www.errors import ActionNotAllowedError, ItemNotFoundError

router = APIRouter()


def urdf_s3_key(robot_class: RobotClass) -> str:
    return f"urdfs/{robot_class.id}/robot.tgz"


def kernel_image_s3_key(robot_class: RobotClass) -> str:
    return f"kernel_images/{robot_class.id}/kernel.png"


@router.get("/")
async def get_robot_classes(
    crud: Annotated[RobotClassCrud, Depends(robot_class_crud)],
) -> list[RobotClass]:
    """Gets all robot classes."""
    return await crud.list_robot_classes()


@router.get("/name/{class_name}")
async def get_robot_class_by_name(
    class_name: str,
    crud: Annotated[RobotClassCrud, Depends(robot_class_crud)],
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
    crud: Annotated[RobotClassCrud, Depends(robot_class_crud)],
) -> list[RobotClass]:
    """Gets a robot class."""
    if user_id.lower() == "me":
        return await crud.list_robot_classes(user.id)
    else:
        return await crud.list_robot_classes(user_id)


@router.put("/{class_name}")
async def add_robot_class(
    class_name: str,
    user: Annotated[User, Depends(require_permissions({"upload"}))],
    crud: Annotated[RobotClassCrud, Depends(robot_class_crud)],
    description: str | None = Query(
        default=None,
        description="The description of the robot class",
    ),
) -> RobotClass:
    """Adds a robot class."""
    return await crud.add_robot_class(class_name, user.id, description)


@router.post("/{class_name}")
async def update_robot_class(
    user: Annotated[User, Depends(require_permissions({"upload"}))],
    existing_robot_class: Annotated[RobotClass, Depends(get_robot_class_by_name)],
    crud: Annotated[RobotClassCrud, Depends(robot_class_crud)],
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
    if existing_robot_class.user_id != user.id:
        raise ActionNotAllowedError("You are not the owner of this robot class")

    return await crud.update_robot_class(
        robot_class=existing_robot_class,
        new_class_name=new_class_name,
        new_description=new_description,
    )


@router.delete("/{class_name}")
async def delete_robot_class(
    user: Annotated[User, Depends(require_permissions({"upload"}))],
    robot_class: Annotated[RobotClass, Depends(get_robot_class_by_name)],
    db_crud: Annotated[RobotClassCrud, Depends(robot_class_crud)],
    fs_crud: Annotated[S3Crud, Depends(s3_crud)],
) -> bool:
    """Deletes a robot class."""
    if robot_class.user_id != user.id:
        raise ActionNotAllowedError("You are not the owner of this robot class")
    s3_key = urdf_s3_key(robot_class)
    await fs_crud.delete_from_s3(s3_key)
    await db_crud.delete_robot_class(robot_class)
    return True


urdf_router = APIRouter()


class RobotDownloadURDFResponse(BaseModel):
    url: str
    md5_hash: str


@urdf_router.get("/{class_name}")
async def get_urdf_for_robot(
    robot_class: Annotated[RobotClass, Depends(get_robot_class_by_name)],
    fs_crud: Annotated[S3Crud, Depends(s3_crud)],
) -> RobotDownloadURDFResponse:
    s3_key = urdf_s3_key(robot_class)
    url, md5_hash = await asyncio.gather(
        fs_crud.generate_presigned_download_url(s3_key),
        fs_crud.get_file_hash(s3_key),
    )
    return RobotDownloadURDFResponse(url=url, md5_hash=md5_hash)


class RobotUploadURDFResponse(BaseModel):
    url: str
    filename: str
    content_type: str


@urdf_router.put("/{class_name}")
async def upload_urdf_for_robot(
    filename: str,
    content_type: str,
    robot_class: Annotated[RobotClass, Depends(get_robot_class_by_name)],
    fs_crud: Annotated[S3Crud, Depends(s3_crud)],
) -> RobotUploadURDFResponse:
    # Checks that the content type is .tgz file.
    if content_type != "application/x-compressed-tar":
        raise ValueError(f"Invalid content type: {content_type}")
    if not filename.lower().endswith(".tgz"):
        raise ValueError(f"Invalid filename: {filename}")
    s3_key = urdf_s3_key(robot_class)
    url = await fs_crud.generate_presigned_upload_url(filename, s3_key, content_type)
    return RobotUploadURDFResponse(url=url, filename=filename, content_type=content_type)


@urdf_router.delete("/{class_name}")
async def delete_urdf_for_robot(
    robot_class: Annotated[RobotClass, Depends(get_robot_class_by_name)],
    fs_crud: Annotated[S3Crud, Depends(s3_crud)],
) -> bool:
    s3_key = urdf_s3_key(robot_class)
    await fs_crud.delete_from_s3(s3_key)
    return True


router.include_router(urdf_router, prefix="/urdf", dependencies=[Depends(require_permissions({"upload"}))])
