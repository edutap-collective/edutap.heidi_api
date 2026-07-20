"""Tests for the OAuth2 token lifecycle."""

from collections.abc import AsyncIterator

import anyio
import httpx
import pytest
import respx
from pydantic import SecretStr

from edutap.heidi_api.auth import TokenManager
from edutap.heidi_api.exceptions import HeidiAuthError
from edutap.heidi_api.settings import HeidiSettings

pytestmark = pytest.mark.anyio

BASE_URL = "https://api.example.org"
TOKEN_URL = f"{BASE_URL}/security/token"


@pytest.fixture
def settings() -> HeidiSettings:
    return HeidiSettings(
        base_url="https://api.example.org",
        username="ada",
        password=SecretStr("s3cret"),
    )


@pytest.fixture
async def http_client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        yield client


async def test_token_is_fetched_on_first_use(
    settings: HeidiSettings, http_client: httpx.AsyncClient
) -> None:
    with respx.mock(assert_all_called=True) as mock:
        route = mock.post(TOKEN_URL).respond(
            json={"access_token": "token-1", "token_type": "bearer"}
        )
        manager = TokenManager(settings, http_client)

        assert await manager.token() == "token-1"

    request = route.calls[0].request
    assert request.headers["content-type"] == "application/x-www-form-urlencoded"
    assert request.content == b"grant_type=password&username=ada&password=s3cret"


async def test_token_is_cached(
    settings: HeidiSettings, http_client: httpx.AsyncClient
) -> None:
    with respx.mock as mock:
        route = mock.post(TOKEN_URL).respond(
            json={"access_token": "token-1", "token_type": "bearer"}
        )
        manager = TokenManager(settings, http_client)

        assert await manager.token() == "token-1"
        assert await manager.token() == "token-1"

    assert route.call_count == 1


async def test_refresh_fetches_a_new_token(
    settings: HeidiSettings, http_client: httpx.AsyncClient
) -> None:
    with respx.mock as mock:
        mock.post(TOKEN_URL).mock(
            side_effect=[
                httpx.Response(
                    200, json={"access_token": "token-1", "token_type": "bearer"}
                ),
                httpx.Response(
                    200, json={"access_token": "token-2", "token_type": "bearer"}
                ),
            ]
        )
        manager = TokenManager(settings, http_client)
        first = await manager.token()

        assert await manager.refresh(first) == "token-2"
        assert await manager.token() == "token-2"


async def test_refresh_is_skipped_when_another_task_already_refreshed(
    settings: HeidiSettings, http_client: httpx.AsyncClient
) -> None:
    with respx.mock as mock:
        route = mock.post(TOKEN_URL).mock(
            side_effect=[
                httpx.Response(
                    200, json={"access_token": "token-1", "token_type": "bearer"}
                ),
                httpx.Response(
                    200, json={"access_token": "token-2", "token_type": "bearer"}
                ),
            ]
        )
        manager = TokenManager(settings, http_client)
        stale = await manager.token()

        async with anyio.create_task_group() as task_group:
            task_group.start_soon(manager.refresh, stale)
            task_group.start_soon(manager.refresh, stale)

        assert await manager.token() == "token-2"

    assert route.call_count == 2  # initial fetch plus exactly one refresh


async def test_rejected_credentials_raise_an_auth_error(
    settings: HeidiSettings, http_client: httpx.AsyncClient
) -> None:
    with respx.mock as mock:
        mock.post(TOKEN_URL).respond(401, text="bad credentials")
        manager = TokenManager(settings, http_client)

        with pytest.raises(HeidiAuthError):
            await manager.token()


async def test_server_error_while_fetching_the_token_is_raised(
    settings: HeidiSettings, http_client: httpx.AsyncClient
) -> None:
    from edutap.heidi_api.exceptions import HeidiServerError

    with respx.mock as mock:
        mock.post(TOKEN_URL).respond(500, text="boom")
        manager = TokenManager(settings, http_client)

        with pytest.raises(HeidiServerError):
            await manager.token()
