"""Unit tests for the robot class router."""

import hashlib

import httpx
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


@pytest.mark.asyncio
async def test_urdf(test_client: TestClient) -> None:
    # Adds a robot class.
    response = test_client.put("/robots/add", params={"class_name": "test"}, headers=HEADERS)
    assert response.status_code == status.HTTP_200_OK, response.text

    # Uploads a URDF for the robot class.
    response = test_client.put(
        "/robots/urdf/test",
        params={
            "filename": "robot.urdf",
            "content_type": "application/gzip",
        },
        headers=HEADERS,
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()
    assert data["url"] is not None

    # Uploads a URDF for the robot class.
    async with httpx.AsyncClient() as client:
        response = await client.put(
            url=data["url"],
            files={"file": ("robot.urdf", b"test", data["content_type"])},
            headers={"Content-Type": data["content_type"]},
        )
        assert response.status_code == status.HTTP_200_OK, response.text

    # Gets the URDF for the robot class.
    response = test_client.get("/robots/urdf/test", headers=HEADERS)
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()
    assert data["url"] is not None

    # Downloads the URDF from the presigned URL.
    async with httpx.AsyncClient() as client:
        response = await client.get(data["url"])
        assert response.status_code == status.HTTP_200_OK, response.text
        content = await response.aread()
    assert data["md5_hash"] == f'"{hashlib.md5(content).hexdigest()}"'

    # Deletes the robot classes.
    response = test_client.delete("/robots/delete", params={"class_name": "test"}, headers=HEADERS)
    assert response.status_code == status.HTTP_200_OK, response.text

    # Check that the URDF is deleted.
    response = test_client.get("/robots/urdf/test", headers=HEADERS)
    assert response.status_code == status.HTTP_404_NOT_FOUND, response.text


@pytest.mark.asyncio
async def test_kernel(test_client: TestClient) -> None:
    # Adds a robot class.
    response = test_client.put("/robots/add", params={"class_name": "test"}, headers=HEADERS)
    assert response.status_code == status.HTTP_200_OK, response.text

    # Uploads a kernel for the robot class
    response = test_client.put(
        "/robots/kernel/test",
        params={
            "filename": "kernel.so",
            "content_type": "application/x-sharedlib",
        },
        headers=HEADERS,
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()
    assert data["url"] is not None

    # Uploads the kernel file using the presigned URL
    async with httpx.AsyncClient() as client:
        response = await client.put(
            url=data["url"],
            files={"file": ("kernel.so", b"test", data["content_type"])},
            headers={"Content-Type": data["content_type"]},
        )
        assert response.status_code == status.HTTP_200_OK, response.text

    # Gets the kernel for the robot class
    response = test_client.get("/robots/kernel/test", headers=HEADERS)
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()
    assert data["url"] is not None

    # Downloads the kernel from the presigned URL
    async with httpx.AsyncClient() as client:
        response = await client.get(data["url"])
        assert response.status_code == status.HTTP_200_OK, response.text
        content = await response.aread()
    assert data["md5_hash"] == f'"{hashlib.md5(content).hexdigest()}"'

    # Deletes the robot class
    response = test_client.delete("/robots/delete", params={"class_name": "test"}, headers=HEADERS)
    assert response.status_code == status.HTTP_200_OK, response.text

    # Check that the kernel is deleted
    response = test_client.get("/robots/kernel/test", headers=HEADERS)
    assert response.status_code == status.HTTP_404_NOT_FOUND, response.text
