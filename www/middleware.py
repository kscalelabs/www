"""Defines the middleware for the FastAPI app."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from www.settings import env


def add_middleware(app: FastAPI) -> None:
    """Adds the middleware to the FastAPI app."""
    # Adds CORS middleware.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add authentication middleware.
    app.add_middleware(
        SessionMiddleware,
        secret_key=env.middleware.secret_key,
        max_age=24 * 60 * 60,  # 1 day
    )
