"""Shared pytest fixtures."""

from collections.abc import AsyncIterator, Iterator

import httpx
import pytest
import respx
from pydantic import SecretStr

from edutap.heidi_api.client import HeidiClient
from edutap.heidi_api.settings import HeidiSettings

BASE_URL = "https://api.example.org"


@pytest.fixture
def anyio_backend() -> str:
    """Run every anyio test on asyncio only, not on trio."""
    return "asyncio"


@pytest.fixture
def settings() -> HeidiSettings:
    return HeidiSettings(
        base_url=BASE_URL,
        username="ada",
        password=SecretStr("s3cret"),
    )


@pytest.fixture
def mock_api() -> Iterator[respx.MockRouter]:
    """Mock every HTTP call and pre-answer the token endpoint."""
    with respx.mock(base_url=BASE_URL, assert_all_called=False) as router:
        router.post("/security/token").respond(
            json={"access_token": "token-1", "token_type": "bearer"}
        )
        yield router


@pytest.fixture
async def heidi(
    settings: HeidiSettings, mock_api: respx.MockRouter
) -> AsyncIterator[HeidiClient]:
    async with HeidiClient(settings=settings) as client:
        yield client


@pytest.fixture
def external_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=BASE_URL)


@pytest.fixture
def anonymous_settings() -> HeidiSettings:
    """Settings for a client built for pure self-service use, no credentials."""
    return HeidiSettings(base_url=BASE_URL, username=None, password=None)


@pytest.fixture
async def anonymous_heidi(
    anonymous_settings: HeidiSettings, mock_api: respx.MockRouter
) -> AsyncIterator[HeidiClient]:
    async with HeidiClient(settings=anonymous_settings) as client:
        yield client
