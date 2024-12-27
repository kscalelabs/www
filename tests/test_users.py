"""Runs tests on the user APIs."""

from fastapi import status
from fastapi.testclient import TestClient
from pytest_mock.plugin import MockType


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
        to="github-user@kscale.dev",  # Using consistent mock email from GitHub OAuth
    )

    # Tries deleting the user again, which should fail.
    response = test_client.delete("/users/me", headers=auth_headers)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.json()
    assert response.json()["detail"] == "Not authenticated"


async def test_user_general_functions(test_client: TestClient) -> None:
    # Because of the way we patched GitHub functions for mocking, it doesn't matter what token we pass in.
    response = test_client.post("/auth/github/code", json={"code": "test_code"})
    assert response.status_code == status.HTTP_200_OK, response.json()
    token = response.json()["api_key"]
    auth_headers = {"Authorization": f"Bearer {token}"}

    # Update the user's profile (e.g., change first_name).
    update_data = {"first_name": "UpdatedFirstName", "last_name": "UpdatedLastName"}
    response = test_client.put("/users/me", headers=auth_headers, json=update_data)
    assert response.status_code == status.HTTP_200_OK, response.json()

    # Verify that the user's profile has been updated.
    response = test_client.get("/users/me", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK, response.json()
    updated_user_data = response.json()
    assert updated_user_data["first_name"] == "UpdatedFirstName"
    assert updated_user_data["last_name"] == "UpdatedLastName"

    # Delete the user when finished.
    response = test_client.delete("/users/me", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK, response.json()
    assert response.json() is True


async def test_oauth_signup_notifications(test_client: TestClient, mock_send_email: MockType) -> None:
    """Test that signup notification emails are sent when users sign up via OAuth."""
    mock_send_email.reset_mock()

    # Test GitHub signup
    response = test_client.post("/auth/github/code", json={"code": "test_code"})
    assert response.status_code == status.HTTP_200_OK, response.json()
    mock_send_email.assert_called_with(
        subject="Welcome to K-Scale Labs",
        body=mock_send_email.call_args[1]["body"],  # Don't compare exact HTML
        to="github-user@kscale.dev",  # Mock GitHub user email
    )

    # Delete the user when finished.
    token = response.json()["api_key"]
    auth_headers = {"Authorization": f"Bearer {token}"}
    response = test_client.delete("/users/me", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK, response.json()
    assert response.json() is True

    # Reset mock for next test
    mock_send_email.reset_mock()

    # Test Google signup with different user
    response = test_client.post("/auth/google/login", json={"token": "test_code"})
    assert response.status_code == status.HTTP_200_OK, response.json()
    mock_send_email.assert_called_with(
        subject="Welcome to K-Scale Labs",
        body=mock_send_email.call_args[1]["body"],  # Don't compare exact HTML
        to="google-user@kscale.dev",  # Mock Google user email
    )

    # Delete the user when finished.
    token = response.json()["api_key"]
    auth_headers = {"Authorization": f"Bearer {token}"}
    response = test_client.delete("/users/me", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK, response.json()
    assert response.json() is True
