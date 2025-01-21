"""Unit tests for the robot router."""

import pytest
from fastapi import status
from fastapi.testclient import TestClient

HEADERS = {"Authorization": "Bearer test"}


@pytest.mark.asyncio
async def test_robots(test_client: TestClient) -> None:
    # First create a robot class that we'll use
    response = test_client.put("/robots/test_class", json={"description": "Test description"}, headers=HEADERS)
    assert response.status_code == status.HTTP_200_OK, response.text
    robot_class_data = response.json()
    assert robot_class_data["id"] is not None

    # Adds a robot
    response = test_client.put(
        "/robot/test_robot",
        json={"description": "Test description", "class_name": "test_class"},
        headers=HEADERS,
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()
    robot_id = data["id"]
    assert robot_id is not None
    assert data["robot_name"] == "test_robot"
    assert data["class_name"] == "test_class"

    # Attempts to add a second robot with the same name
    response = test_client.put(
        "/robot/test_robot",
        json={"description": "Test description", "class_name": "test_class"},
        headers=HEADERS,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text

    # Gets all robots
    response = test_client.get("/robot", headers=HEADERS)
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()
    assert len(data) == 1
    assert data[0]["robot_name"] == "test_robot"

    # Gets the robot by name
    response = test_client.get("/robot/name/test_robot", headers=HEADERS)
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()
    assert data["robot_name"] == "test_robot"

    # Gets the robot by ID
    response = test_client.get(f"/robot/id/{robot_id}", headers=HEADERS)
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()
    assert data["robot_name"] == "test_robot"

    # Adds a second robot
    response = test_client.put(
        "/robot/other_robot",
        json={"description": "Test description", "class_name": "test_class"},
        headers=HEADERS,
    )
    assert response.status_code == status.HTTP_200_OK, response.text

    # Updates the first robot
    response = test_client.post(
        "/robot/test_robot",
        json={
            "new_robot_name": "updated_robot",
            "new_description": "new description",
        },
        headers=HEADERS,
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()
    assert data["robot_name"] == "updated_robot"
    assert data["description"] == "new description"

    # Lists my robots
    response = test_client.get("/robot/user/me", headers=HEADERS)
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()
    assert len(data) == 2
    assert all(robot["robot_name"] in ("updated_robot", "other_robot") for robot in data)

    # Deletes the robots
    response = test_client.delete("/robot/updated_robot", headers=HEADERS)
    assert response.status_code == status.HTTP_200_OK, response.text

    # Lists my robots again
    response = test_client.get("/robot/user/me", headers=HEADERS)
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()
    assert len(data) == 1
    assert data[0]["robot_name"] == "other_robot"

    # Clean up - delete remaining robot and robot class
    response = test_client.get("/robot/name/other_robot", headers=HEADERS)
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()
    assert data["id"] is not None

    response = test_client.delete("/robot/other_robot", headers=HEADERS)
    assert response.status_code == status.HTTP_200_OK, response.text

    response = test_client.delete("/robots/test_class", headers=HEADERS)
    assert response.status_code == status.HTTP_200_OK, response.text
