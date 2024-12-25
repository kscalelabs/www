"""Defines the test authentication endpoint for staging environment."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from www.app.crud.users import UserCrud
from www.app.model import APIKeySource
from www.settings import settings

router = APIRouter()


class TestAuthResponse(BaseModel):
    """Response model for test authentication endpoint."""

    user_id: str
    token: str


@router.post("/test", response_model=TestAuthResponse)
async def test_auth_endpoint(user_crud: Annotated[UserCrud, Depends()]) -> TestAuthResponse:
    """Authenticates as a test user in staging environment.

    This endpoint is only available in development and staging environments.
    It creates (or reuses) a test user account and returns authentication credentials.
    """
    # Only allow in development/staging environments
    if settings.environment not in ["development", "staging"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Test auth endpoint not available in this environment",
        )

    # Attempt to find or create the test user
    test_email = "dummytest@staging.local"
    test_password = "dummy-test-password-123"  # Password doesn't matter as we use API key

    existing_user = await user_crud.get_user_from_email(test_email)
    if not existing_user:
        # Create new test user if it doesn't exist
        existing_user = await user_crud._create_user_from_email(test_email, test_password)

    # Generate an API key for the test user
    api_key = await user_crud.add_api_key(
        existing_user.id,
        source=APIKeySource("password"),
        permissions="full",  # Test user gets full permissions like normal users
    )

    return TestAuthResponse(user_id=existing_user.id, token=api_key.id)
