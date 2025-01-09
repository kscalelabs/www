"""Unit tests for the robot class router."""

import pytest
from fastapi import status
from fastapi.testclient import TestClient

HEADERS = {"Authorization": "Bearer test"}


@pytest.mark.asyncio
async def test_robot_classes(test_client: TestClient) -> None:
    # Adds a robot class.
    response = test_client.put("/robots/add", params={"class_name": "test"}, headers=HEADERS)
    assert response.status_code == status.HTTP_200_OK, response.text

    # Attempts to add a second robot class with the same name.
    response = test_client.put("/robots/add", params={"class_name": "test"}, headers=HEADERS)
    assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text

    # Gets the added robot class.
    response = test_client.get("/robots", headers=HEADERS)
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()
    assert len(data) == 1
    assert data[0]["class_name"] == "test"

    # Gets the robot class by name.
    response = test_client.get("/robots/name/test", headers=HEADERS)
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()
    assert data["class_name"] == "test"

    # Adds a second robot class.
    response = test_client.put("/robots/add", params={"class_name": "othertest"}, headers=HEADERS)
    assert response.status_code == status.HTTP_200_OK, response.text

    # Updates the robot class.
    response = test_client.put(
        "/robots/update",
        params={
            "class_name": "test",
            "new_class_name": "othertest",
            "new_description": "new description",
        },
        headers=HEADERS,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text

    # Updates the robot class.
    response = test_client.put(
        "/robots/update",
        params={
            "class_name": "test",
            "new_class_name": "newtest",
            "new_description": "new description",
        },
        headers=HEADERS,
    )
    assert response.status_code == status.HTTP_200_OK, response.text

    # Lists my robot classes.
    response = test_client.get("/robots/user/me", headers=HEADERS)
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()
    assert len(data) == 2
    assert all(robot_class["class_name"] in ("newtest", "othertest") for robot_class in data)

    # Deletes the robot classes.
    response = test_client.delete("/robots/delete", params={"class_name": "newtest"}, headers=HEADERS)
    assert response.status_code == status.HTTP_200_OK, response.text

    response = test_client.delete("/robots/delete", params={"class_name": "othertest"}, headers=HEADERS)
    assert response.status_code == status.HTTP_200_OK, response.text

    # Lists my robot classes.
    response = test_client.get("/robots/user/me", headers=HEADERS)
    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json() == []
