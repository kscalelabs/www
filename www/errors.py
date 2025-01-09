"""Defines common errors used by the application."""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from www.settings import env


class ItemNotFoundError(ValueError): ...


class ActionNotAllowedError(ValueError): ...


class InvalidNameError(ValueError): ...


def add_exception_handlers(app: FastAPI) -> None:
    """Adds the handlers to the FastAPI app."""
    show_full_error = env.site.is_test_environment

    def protected_str(exc: Exception) -> str:
        if show_full_error:
            return str(exc)
        return "The request was invalid."

    async def value_error_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": "The request was invalid.", "detail": protected_str(exc)},
        )

    app.add_exception_handler(ValueError, value_error_exception_handler)

    async def runtime_error_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": "An internal error occurred.", "detail": protected_str(exc)},
        )

    app.add_exception_handler(RuntimeError, runtime_error_exception_handler)

    async def item_not_found_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"message": "Item not found.", "detail": str(exc)},
        )

    app.add_exception_handler(ItemNotFoundError, item_not_found_exception_handler)

    async def action_not_allowed_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"message": "Action not allowed.", "detail": str(exc)},
        )

    app.add_exception_handler(ActionNotAllowedError, action_not_allowed_exception_handler)

    async def invalid_name_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": "Invalid name.", "detail": str(exc)},
        )

    app.add_exception_handler(InvalidNameError, invalid_name_exception_handler)
