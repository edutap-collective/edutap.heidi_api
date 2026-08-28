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
    """Two concurrent ``refresh()`` calls must genuinely overlap.

    A mocked response that resolves without ever suspending would let the
    first ``refresh()`` run check-then-act to completion before the second
    one is even scheduled -- masking a missing lock. To rule that out, the
    mocked token route's first refresh response only comes back after an
    ``anyio.Event`` is set, forcing a real event-loop handoff while that
    call is still inside its critical section deciding whether to fetch.
    """
    first_refresh_in_flight = anyio.Event()
    release_first_refresh = anyio.Event()
    call_count = 0

    async def respond(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # The initial `manager.token()` fetch, before any concurrency.
            return httpx.Response(
                200, json={"access_token": "token-1", "token_type": "bearer"}
            )
        if call_count == 2:
            # The first of the two concurrent refresh() calls to reach the
            # network. Suspend here for real, so the event loop is forced to
            # run the second refresh() call (or block it on the lock) while
            # this one is still mid-fetch.
            first_refresh_in_flight.set()
            await release_first_refresh.wait()
            return httpx.Response(
                200, json={"access_token": "token-2", "token_type": "bearer"}
            )
        # Only reachable if the check-then-act race was left unguarded: a
        # second, unwanted refresh request went out.
        return httpx.Response(
            200, json={"access_token": "token-3", "token_type": "bearer"}
        )

    with respx.mock as mock:
        route = mock.post(TOKEN_URL).mock(side_effect=respond)
        manager = TokenManager(settings, http_client)
        stale = await manager.token()

        async def run_refresh() -> None:
            await manager.refresh(stale)

        with anyio.fail_after(5):
            async with anyio.create_task_group() as task_group:
                task_group.start_soon(run_refresh)
                task_group.start_soon(run_refresh)
                await first_refresh_in_flight.wait()
                # Give the second refresh() call a genuine chance to run while
                # the first is still suspended mid-fetch.
                await anyio.sleep(0)
                release_first_refresh.set()

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


async def test_fetching_a_token_without_credentials_raises_a_clear_auth_error(
    http_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Settings for pure self-service use carry no credentials.

    Requesting a token from such settings must fail with an actionable
    :class:`HeidiAuthError`, not an ``AttributeError`` on ``None`` and not a
    request sent with ``None`` as the username/password.
    """
    monkeypatch.delenv("HEIDI_USERNAME", raising=False)
    monkeypatch.delenv("HEIDI_PASSWORD", raising=False)
    settings = HeidiSettings(base_url=BASE_URL, _env_file=None)

    with respx.mock(assert_all_mocked=True) as mock:
        manager = TokenManager(settings, http_client)

        with pytest.raises(HeidiAuthError, match="HEIDI_USERNAME|HEIDI_PASSWORD"):
            await manager.token()

    assert mock.calls.call_count == 0
