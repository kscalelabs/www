"""Runs tests on the user APIs."""

from fastapi import status
from fastapi.testclient import TestClient
from httpx import AsyncClient
from pytest_mock.plugin import MockType

from www.app.db import create_tables


def test_user_auth_functions(test_client: TestClient, mock_send_email: MockType) -> None:
    # Checks that without the session token we get a 401 response.
    response = test_client.get("/users/me")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.json()
    assert response.json()["detail"] == "Not authenticated"

    # Checks that we can't log the user out without the session token.
    response = test_client.delete("/auth/api/logout")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.json()

    # Because of the way we patched GitHub functions for mocking, it doesn't matter what token we pass in.
    response = test_client.post("/auth/github/code", json={"code": "test_code"})
    assert response.status_code == status.HTTP_200_OK, response.json()
    token = response.json()["api_key"]
    auth_headers = {"Authorization": f"Bearer {token}"}

    # Checks that with the session token we get a 200 response.
    response = test_client.get("/users/me", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK, response.json()

    # Log the user out, which deletes the session token.
    response = test_client.delete("/auth/api/logout", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK, response.json()
    assert response.json() is True

    # Checks that we can no longer use that session token to get the user's info.
    response = test_client.get("/users/me", headers=auth_headers)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.json()
    assert response.json()["detail"] == "Not authenticated"

    # Log the user back in, getting new session token.
    response = test_client.post("/auth/github/code", json={"code": "test_code"})
    assert response.status_code == status.HTTP_200_OK, response.json()
    assert response.json()["api_key"] != token
    token = response.json()["api_key"]
    auth_headers = {"Authorization": f"Bearer {token}"}

    # Delete the user using the new session token.
    response = test_client.delete("/users/me", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK, response.json()
    assert response.json() is True
    # Verify delete email was sent
    mock_send_email.assert_called_with(
        subject="Account Deleted - K-Scale Labs",
        body=mock_send_email.call_args[1]["body"],  # Don't compare exact HTML
        to="dchen@kscale.dev",  # This is the mock email from conftest.py
    )

    # Tries deleting the user again, which should fail.
    response = test_client.delete("/users/me", headers=auth_headers)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.json()
    assert response.json()["detail"] == "Not authenticated"


async def test_user_general_functions(app_client: AsyncClient) -> None:
    await create_tables()

    # Because of the way we patched GitHub functions for mocking, it doesn't matter what token we pass in.
    response = await app_client.post("/auth/github/code", json={"code": "test_code"})
    assert response.status_code == status.HTTP_200_OK, response.json()
    token = response.json()["api_key"]
    auth_headers = {"Authorization": f"Bearer {token}"}

    # Update the user's profile (e.g., change first_name).
    update_data = {"first_name": "UpdatedFirstName", "last_name": "UpdatedLastName"}
    response = await app_client.put("/users/me", headers=auth_headers, json=update_data)
    assert response.status_code == status.HTTP_200_OK, response.json()

    # Verify that the user's profile has been updated.
    response = await app_client.get("/users/me", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK, response.json()
    updated_user_data = response.json()
    assert updated_user_data["first_name"] == "UpdatedFirstName"
    assert updated_user_data["last_name"] == "UpdatedLastName"


async def test_oauth_signup_notifications(app_client: AsyncClient, mock_send_email: MockType) -> None:
    """Test that signup notification emails are sent when users sign up via OAuth."""
    await create_tables()
    mock_send_email.reset_mock()

    # Test GitHub signup
    response = await app_client.post("/auth/github/code", json={"code": "test_code"})
    assert response.status_code == status.HTTP_200_OK, response.json()
    mock_send_email.assert_called_with(
        subject="Welcome to K-Scale Labs",
        body=mock_send_email.call_args[1]["body"],  # Don't compare exact HTML
        to="github-user@kscale.dev",  # Mock GitHub user email
    )

    # Reset mock for next test
    mock_send_email.reset_mock()

    # Test Google signup with different user
    response = await app_client.post("/auth/google/code", json={"code": "test_code"})
    assert response.status_code == status.HTTP_200_OK, response.json()
    mock_send_email.assert_called_with(
        subject="Welcome to K-Scale Labs",
        body=mock_send_email.call_args[1]["body"],  # Don't compare exact HTML
        to="google-user@kscale.dev",  # Mock Google user email
    )
