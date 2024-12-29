"""Defines the main entrypoint for the FastAPI app."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyCookie, APIKeyHeader

from www.app.db import create_tables
from www.app.errors import (
    BadArtifactError,
    InternalError,
    ItemNotFoundError,
    NotAuthenticatedError,
    NotAuthorizedError,
)
from www.app.routers.artifacts import router as artifacts_router
from www.app.routers.auth import router as auth_router
from www.app.routers.keys import router as keys_router
from www.app.routers.krecs import router as krecs_router
from www.app.routers.listings import router as listings_router
from www.app.routers.onshape import router as onshape_router
from www.app.routers.robots import router as robots_router
from www.app.routers.teleop import router as teleop_router
from www.app.routers.users import router as users_router
from www.utils import get_cors_origins


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initializes the app and creates the database tables."""
    logging.getLogger("aiobotocore").setLevel(logging.CRITICAL)
    await create_tables()
    try:
        yield
    finally:
        pass


# Use APIKeyCookie with the name "AUTH"
cookie_scheme = APIKeyCookie(name="AUTH")

api_key_header = APIKeyHeader(name="Authorization", auto_error=False)

app = FastAPI(
    title="K-Scale",
    version="1.0.0",
    docs_url="/",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Adds CORS middleware.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ValueError)
async def value_error_exception_handler(request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"message": "The request was invalid.", "detail": str(exc)},
    )


@app.exception_handler(ItemNotFoundError)
async def item_not_found_exception_handler(request: Request, exc: ItemNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"message": "Item not found.", "detail": str(exc)},
    )


@app.exception_handler(InternalError)
async def internal_error_exception_handler(request: Request, exc: InternalError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"message": "Internal error.", "detail": str(exc)},
    )


@app.exception_handler(NotAuthenticatedError)
async def not_authenticated_exception_handler(request: Request, exc: NotAuthenticatedError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"message": "Not authenticated.", "detail": str(exc)},
    )


@app.exception_handler(NotAuthorizedError)
async def not_authorized_exception_handler(request: Request, exc: NotAuthorizedError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"message": "Not authorized.", "detail": str(exc)},
    )


@app.exception_handler(BadArtifactError)
async def bad_artifact_exception_handler(request: Request, exc: BadArtifactError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"message": f"Bad artifact: {exc}", "detail": str(exc)},
    )


async def validate_auth_token(auth_token: str = Depends(api_key_header)) -> str:
    if not auth_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing authentication token")
    return auth_token


app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(artifacts_router, prefix="/artifacts", tags=["artifacts"])
app.include_router(keys_router, prefix="/keys", tags=["keys"])
app.include_router(listings_router, prefix="/listings", tags=["listings"])
app.include_router(onshape_router, prefix="/onshape", tags=["onshape"])
app.include_router(robots_router, prefix="/robots", tags=["robots"])
app.include_router(users_router, prefix="/users", tags=["users"])
app.include_router(teleop_router, prefix="/teleop", tags=["teleop"])
app.include_router(krecs_router, prefix="/krecs", tags=["krecs"])

# For running with debugger
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8080)
