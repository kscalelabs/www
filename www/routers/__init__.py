"""Defines the routers for the FastAPI app."""

from fastapi import Depends, FastAPI

from www.auth import require_user

from .auth import router as auth_router
from .robot import router as robot_router
from .robot_class import router as robot_class_router


def add_routers(app: FastAPI) -> None:
    """Adds the routers to the FastAPI app."""
    app.include_router(auth_router, prefix="/auth", tags=["auth"])

    # Mark the non-auth routers as protected.
    app.include_router(robot_router, prefix="/robot", tags=["robot"], dependencies=[Depends(require_user)])
    app.include_router(robot_class_router, prefix="/robots", tags=["robots"])
