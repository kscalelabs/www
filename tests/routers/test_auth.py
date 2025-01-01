"""Tests for the auth router."""

import pytest
from fastapi import status
from fastapi.testclient import TestClient


@pytest.mark.asyncio
async def test_user_endpoint(test_client: TestClient) -> None:
    response = test_client.get("/auth/user")
    assert response.status_code == status.HTTP_200_OK, response.text

    # Matches test user data.
    assert response.json() == {
        "user_id": "test_user",
        "is_admin": True,
        "can_upload": True,
        "can_test": True,
    }


@pytest.mark.asyncio
async def test_profile_endpoint(test_client: TestClient) -> None:
    response = test_client.get("/auth/profile")
    assert response.status_code == status.HTTP_200_OK, response.text

    # Matches test user data.
    assert response.json() == {
        "email": "test@example.com",
        "email_verified": True,
        "user": {
            "user_id": "test_user",
            "is_admin": True,
            "can_upload": True,
            "can_test": True,
        },
    }


@pytest.mark.asyncio
async def test_logout_endpoint(test_client: TestClient) -> None:
    response = test_client.get("/auth/logout")
    assert response.status_code == status.HTTP_200_OK, response.text
