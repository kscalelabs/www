"""Pytest configuration file."""

import logging
import os
from typing import AsyncGenerator, Generator, cast

import pytest
from _pytest.python import Function
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from httpx._transports.asgi import _ASGIApp
from moto.server import ThreadedMotoServer
from pytest_mock.plugin import MockerFixture, MockType

os.environ["ENVIRONMENT"] = "local"


def pytest_collection_modifyitems(items: list[Function]) -> None:
    items.sort(key=lambda x: x.get_closest_marker("slow") is not None)


@pytest.fixture(autouse=True)
def mock_aws() -> Generator[None, None, None]:
    server: ThreadedMotoServer | None = None

    # logging.getLogger("botocore").setLevel(logging.DEBUG)
    logging.getLogger("botocore").setLevel(logging.WARN)

    try:
        env_vars: dict[str, str] = {}
        for k in (
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_ENDPOINT_URL_DYNAMODB",
            "AWS_ENDPOINT_URL_S3",
            "AWS_REGION",
            "AWS_DEFAULT_REGION",
        ):
            if k in os.environ:
                env_vars[k] = os.environ[k]
                del os.environ[k]

        os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
        os.environ["AWS_ACCESS_KEY_ID"] = "test"
        os.environ["AWS_DEFAULT_REGION"] = os.environ["AWS_REGION"] = "us-east-1"
        os.environ["GITHUB_CLIENT_ID"] = "test"
        os.environ["GITHUB_CLIENT_SECRET"] = "test"

        # Starts a local AWS server.
        server = ThreadedMotoServer(port=0)
        server.start()
        host, port = server.get_host_and_port()
        os.environ["AWS_ENDPOINT_URL"] = f"http://{host}:{port}"
        os.environ["AWS_ENDPOINT_URL_DYNAMODB"] = f"http://{host}:{port}"
        os.environ["AWS_ENDPOINT_URL_S3"] = f"http://{host}:{port}"

        yield

    finally:
        if server is not None:
            server.stop()

        for k, v in env_vars.items():
            if v is None:
                os.unsetenv(k)
            else:
                os.environ[k] = v


@pytest.fixture()
async def app_client() -> AsyncGenerator[AsyncClient, None]:
    from www.main import app

    transport = ASGITransport(cast(_ASGIApp, app))

    async with AsyncClient(transport=transport, base_url="http://test") as app_client:
        yield app_client


@pytest.fixture()
def test_client() -> Generator[TestClient, None, None]:
    import asyncio

    from www.db import Crud, create_tables
    from www.main import app

    async def setup() -> None:
        async with Crud() as crud:
            await create_tables(crud)

    asyncio.run(setup())

    with TestClient(app) as client:
        yield client


@pytest.fixture(autouse=True)
def mock_send_email(mocker: MockerFixture) -> MockType:
    mock = mocker.patch("www.utils.email.send_email")
    mock.return_value = None
    return mock
