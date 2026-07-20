"""Tests for transport, authentication wiring and error mapping."""

import httpx
import pytest
import respx

from edutap.heidi_api.client import HeidiClient
from edutap.heidi_api.exceptions import (
    HeidiAuthError,
    HeidiConflictError,
    HeidiNotFoundError,
    HeidiServerError,
    HeidiValidationError,
)
from edutap.heidi_api.models import AuthenticatedUser
from edutap.heidi_api.settings import HeidiSettings

pytestmark = pytest.mark.anyio

BASE_URL = "https://api.example.org"  # must match the value in conftest.py

USER_PAYLOAD = {
    "display_name": "Ada Lovelace",
    "username": "ada",
    "roles": ["issuer"],
    "customer_id": None,
    "customer_display_name": None,
}


async def test_whoami_returns_the_authenticated_user(
    heidi: HeidiClient, mock_api: respx.MockRouter
) -> None:
    mock_api.get("/security/authenticated").respond(json=USER_PAYLOAD)

    user = await heidi.whoami()

    assert isinstance(user, AuthenticatedUser)
    assert user.username == "ada"


async def test_requests_carry_the_bearer_token(
    heidi: HeidiClient, mock_api: respx.MockRouter
) -> None:
    route = mock_api.get("/security/authenticated").respond(json=USER_PAYLOAD)

    await heidi.whoami()

    assert route.calls[0].request.headers["authorization"] == "Bearer token-1"


async def test_a_401_triggers_exactly_one_reauthentication(
    heidi: HeidiClient, mock_api: respx.MockRouter
) -> None:
    token_route = mock_api.post("/security/token").mock(
        side_effect=[
            httpx.Response(
                200, json={"access_token": "token-1", "token_type": "bearer"}
            ),
            httpx.Response(
                200, json={"access_token": "token-2", "token_type": "bearer"}
            ),
        ]
    )
    route = mock_api.get("/security/authenticated").mock(
        side_effect=[
            httpx.Response(401, text="expired"),
            httpx.Response(200, json=USER_PAYLOAD),
        ]
    )

    user = await heidi.whoami()

    assert user.username == "ada"
    assert token_route.call_count == 2
    assert route.calls[1].request.headers["authorization"] == "Bearer token-2"


async def test_a_second_401_raises_an_auth_error(
    heidi: HeidiClient, mock_api: respx.MockRouter
) -> None:
    mock_api.get("/security/authenticated").respond(401, text="nope")

    with pytest.raises(HeidiAuthError):
        await heidi.whoami()


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (404, HeidiNotFoundError),
        (409, HeidiConflictError),
        (422, HeidiValidationError),
        (500, HeidiServerError),
    ],
)
async def test_error_statuses_raise_typed_exceptions(
    heidi: HeidiClient,
    mock_api: respx.MockRouter,
    status_code: int,
    expected: type[Exception],
) -> None:
    mock_api.get("/security/authenticated").respond(status_code, text="failed")

    with pytest.raises(expected):
        await heidi.whoami()


async def test_client_closes_its_own_http_client(
    settings: HeidiSettings, mock_api: respx.MockRouter
) -> None:
    client = HeidiClient(settings=settings)

    async with client:
        pass

    assert client._http_client.is_closed


async def test_an_injected_http_client_is_not_closed(
    settings: HeidiSettings,
    mock_api: respx.MockRouter,
    external_http_client: httpx.AsyncClient,
) -> None:
    async with HeidiClient(settings=settings, http_client=external_http_client):
        pass

    assert not external_http_client.is_closed
    await external_http_client.aclose()


async def test_an_injected_http_client_without_base_url_fails_fast(
    settings: HeidiSettings,
) -> None:
    bare_client = httpx.AsyncClient()

    with pytest.raises(ValueError, match="base_url"):
        HeidiClient(settings=settings, http_client=bare_client)

    await bare_client.aclose()


async def test_an_authenticated_method_without_credentials_raises_a_clear_error(
    anonymous_heidi: HeidiClient, mock_api: respx.MockRouter
) -> None:
    """A client built for pure self-service use has no issuer credentials.

    Calling one of the twelve authenticated operations on it must fail with
    an actionable :class:`HeidiAuthError` naming the missing configuration,
    not an opaque error from deep inside the token fetch.
    """
    with pytest.raises(HeidiAuthError, match="HEIDI_USERNAME|HEIDI_PASSWORD"):
        await anonymous_heidi.whoami()

    assert not any(
        call.request.url.path == "/security/authenticated" for call in mock_api.calls
    )


async def test_settings_are_read_from_the_environment_by_default(
    monkeypatch: pytest.MonkeyPatch, mock_api: respx.MockRouter
) -> None:
    monkeypatch.setenv("HEIDI_BASE_URL", BASE_URL)
    monkeypatch.setenv("HEIDI_USERNAME", "ada")
    monkeypatch.setenv("HEIDI_PASSWORD", "s3cret")
    mock_api.get("/security/authenticated").respond(json=USER_PAYLOAD)

    async with HeidiClient() as client:
        user = await client.whoami()

    assert user.display_name == "Ada Lovelace"
