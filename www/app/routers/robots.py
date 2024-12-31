"""Defines the router endpoints for handling Robots."""

import asyncio
from typing import Annotated, Type

from boto3.dynamodb.conditions import Key
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ValidationError

from www.app.auth import User, get_user
from www.app.crud.base import ItemNotFoundError
from www.app.crud.robots import RobotData, RobotsCrud, robots_crud
from www.app.db import Crud
from www.app.model import Listing, Robot, get_artifact_url

router = APIRouter()


class CreateRobotRequest(BaseModel):
    listing_id: str
    name: str
    description: str | None = None


class CreateRobotResponse(BaseModel):
    robot_id: str


@router.post("/create", response_model=CreateRobotResponse)
async def create_robot(
    request: CreateRobotRequest,
    user: Annotated[User, Depends(get_user)],
    crud: Annotated[RobotsCrud, Depends(robots_crud)],
) -> CreateRobotResponse:
    """Create a new robot."""
    try:
        robot = await crud.create_robot(
            user_id=user.id,
            listing_id=request.listing_id,
            name=request.name,
            description=request.description,
        )
        return CreateRobotResponse(robot_id=robot.id)
    except ItemNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/get/{robot_id}", response_model=Robot)
async def get_robot(
    robot_id: str,
    user: Annotated[User, Depends(get_user)],
    crud: Annotated[RobotsCrud, Depends(robots_crud)],
) -> Robot:
    """Get a specific robot."""
    try:
        robot = await crud.get_robot(robot_id)
        if robot.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this robot")
        return robot
    except ItemNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Robot not found")


class SingleRobotResponse(BaseModel):
    robot_id: str
    user_id: str
    listing_id: str
    name: str
    username: str
    slug: str
    description: str | None
    created_at: int
    is_deleted: bool = False

    @classmethod
    async def from_robot(
        cls: Type["SingleRobotResponse"],
        robot: Robot,
        crud: Crud | None = None,
        listing: Listing | None = None,
        creator: User | None = None,
    ) -> "SingleRobotResponse":
        return cls(
            robot_id=robot.id,
            user_id=robot.user_id,
            listing_id=robot.listing_id,
            name=robot.name,
            username=creator.username if creator else "Deleted User",
            slug=listing.slug if listing else "deleted-listing",
            description=robot.description,
            created_at=robot.created_at,
            is_deleted=creator is None or listing is None or creator.id == "deleted",
        )


class RobotListResponse(BaseModel):
    robots: list[SingleRobotResponse]


@router.get("/list", response_model=RobotListResponse)
async def list_user_robots(
    user: User = Depends(get_user),
    crud: RobotsCrud = Depends(robots_crud),
) -> RobotListResponse:
    """List all robots for the current user."""
    robots = await crud.get_robots_by_user_id(user.id)
    if not robots:
        return RobotListResponse(robots=[])

    unique_listing_ids = list(set(robot.listing_id for robot in robots))
    listings = await crud.get_listings_by_ids(unique_listing_ids)
    listing_ids_to_listing = {listing.id: listing for listing in listings}

    deleted_user = User(
        id="deleted",
        username="Deleted User",
        email="",
        created_at=0,
        updated_at=0,
    )

    listing_creators = await crud.get_user_batch(list(set(listing.user_id for listing in listings)))
    user_id_to_user = {user.id: user for user in listing_creators}

    async def get_robot_response(robot: Robot) -> SingleRobotResponse:
        listing = listing_ids_to_listing.get(robot.listing_id)
        if listing:
            creator = user_id_to_user.get(listing.user_id, deleted_user)
        else:
            listing = Listing(
                id=robot.listing_id,
                user_id="deleted",
                name="Deleted Listing",
                description="This listing has been deleted",
                slug="deleted-listing",
                child_ids=[],
                created_at=robot.created_at,
                updated_at=robot.created_at,
            )
            creator = deleted_user

        return await SingleRobotResponse.from_robot(
            robot,
            crud=crud,
            listing=listing,
            creator=creator,
        )

    robot_responses = await asyncio.gather(*(get_robot_response(robot) for robot in robots))
    return RobotListResponse(robots=list(robot_responses))


class UpdateRobotRequest(BaseModel):
    name: str | None = None
    description: str | None = None


@router.put("/update/{robot_id}", response_model=Robot)
async def update_robot(
    robot_id: str,
    update_data: UpdateRobotRequest,
    user: User = Depends(get_user),
    crud: RobotsCrud = Depends(robots_crud),
) -> Robot:
    """Update a robot's information."""
    try:
        robot = await crud.get_robot(robot_id)
        if robot.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to update this robot")

        # Convert the update data to a properly typed RobotData dict
        update_dict: RobotData = {
            "user_id": robot.user_id,  # Required field in RobotData
            "listing_id": robot.listing_id,  # Required field in RobotData
            "name": update_data.name if update_data.name is not None else robot.name,
        }
        if update_data.description is not None:
            update_dict["description"] = update_data.description

        updated_robot = await crud.update_robot(robot_id, update_dict)
        return updated_robot
    except ItemNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Robot not found")


@router.delete("/delete/{robot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_robot(
    robot_id: str,
    user: User = Depends(get_user),
    crud: RobotsCrud = Depends(robots_crud),
) -> None:
    """Delete a robot."""
    try:
        robot = await crud.get_robot(robot_id)
        if not robot:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Robot not found")
        if robot.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this robot")

        await crud.delete_robot(robot)
    except ItemNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Robot not found")


class RobotURDFResponse(BaseModel):
    urdf_url: str | None


@router.get("/urdf/{listing_id}", response_model=RobotURDFResponse)
async def get_robot_urdf(
    listing_id: str,
    crud: RobotsCrud = Depends(robots_crud),
) -> RobotURDFResponse:
    """Get the URDF for a robot."""
    artifacts = await crud.get_listing_artifacts(
        listing_id,
        additional_filter_expression=Key("artifact_type").eq("tgz"),
    )
    if len(artifacts) == 0:
        return RobotURDFResponse(urdf_url=None)
    first_artifact = min(artifacts, key=lambda a: a.timestamp)
    return RobotURDFResponse(urdf_url=get_artifact_url(artifact=first_artifact))
