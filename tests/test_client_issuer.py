"""Tests for the issuer endpoints."""

from uuid import UUID

import pytest
import respx

from edutap.heidi_api.client import HeidiClient
from edutap.heidi_api.models import (
    PassData,
    PassOperationResponse,
    PassState,
    PassTemplate,
    WalletType,
)

pytestmark = pytest.mark.anyio

PASS_ID = "11111111-1111-1111-1111-111111111111"  # noqa: S105 -- a UUID, not a credential
TEMPLATE_ID = "22222222-2222-2222-2222-222222222222"
PERSON_ID = "person-42"

PASS_PAYLOAD = {
    "pass_id": PASS_ID,
    "person_id": PERSON_ID,
    "template_id": TEMPLATE_ID,
    "wallet_type": "APPLE",
    "pass_state": "Active",
    "last_update": "2026-07-20T10:11:12Z",
    "install_link": "https://example.org/install",
}
OPERATION_PAYLOAD = {"pass_id": PASS_ID, "detail": "accepted"}


async def test_get_pass(heidi: HeidiClient, mock_api: respx.MockRouter) -> None:
    mock_api.get(f"/api/v1/pass/{PASS_ID}").respond(json=PASS_PAYLOAD)

    result = await heidi.get_pass(PASS_ID)

    assert isinstance(result, PassData)
    assert result.pass_state is PassState.ACTIVE
    assert result.install_link == "https://example.org/install"


async def test_update_pass(heidi: HeidiClient, mock_api: respx.MockRouter) -> None:
    mock_api.put(f"/api/v1/pass/{PASS_ID}").respond(202, json=OPERATION_PAYLOAD)

    result = await heidi.update_pass(PASS_ID)

    assert isinstance(result, PassOperationResponse)
    assert result.detail == "accepted"


async def test_delete_pass(heidi: HeidiClient, mock_api: respx.MockRouter) -> None:
    mock_api.delete(f"/api/v1/pass/{PASS_ID}").respond(202, json=OPERATION_PAYLOAD)

    result = await heidi.delete_pass(PASS_ID)

    assert result.detail == "accepted"


async def test_create_pass_sends_the_operation_body(
    heidi: HeidiClient, mock_api: respx.MockRouter
) -> None:
    route = mock_api.post("/api/v1/pass").respond(202, json=OPERATION_PAYLOAD)

    result = await heidi.create_pass(
        template_id=TEMPLATE_ID,
        person_id=PERSON_ID,
        wallet_type=WalletType.APPLE,
    )

    assert result.detail == "accepted"
    import json

    assert json.loads(route.calls[0].request.content) == {
        "wallet_type": "APPLE",
        "template_id": TEMPLATE_ID,
        "person_id": PERSON_ID,
    }


async def test_create_pass_accepts_a_plain_string_wallet_type(
    heidi: HeidiClient, mock_api: respx.MockRouter
) -> None:
    route = mock_api.post("/api/v1/pass").respond(202, json=OPERATION_PAYLOAD)

    await heidi.create_pass(
        template_id=TEMPLATE_ID, person_id=PERSON_ID, wallet_type="GOOGLE"
    )

    import json

    assert json.loads(route.calls[0].request.content)["wallet_type"] == "GOOGLE"


async def test_get_passes_returns_a_list(
    heidi: HeidiClient, mock_api: respx.MockRouter
) -> None:
    mock_api.get(f"/api/v1/passes/{TEMPLATE_ID}/{PERSON_ID}").respond(
        json=[PASS_PAYLOAD]
    )

    result = await heidi.get_passes(TEMPLATE_ID, PERSON_ID)

    assert [item.pass_id for item in result] == [UUID(PASS_ID)]
    assert isinstance(result[0], PassData)


async def test_update_passes(heidi: HeidiClient, mock_api: respx.MockRouter) -> None:
    mock_api.put(f"/api/v1/passes/{TEMPLATE_ID}/{PERSON_ID}").respond(
        202, json=OPERATION_PAYLOAD
    )

    result = await heidi.update_passes(TEMPLATE_ID, PERSON_ID)

    assert result.detail == "accepted"


async def test_delete_passes(heidi: HeidiClient, mock_api: respx.MockRouter) -> None:
    mock_api.delete(f"/api/v1/passes/{TEMPLATE_ID}/{PERSON_ID}").respond(
        202, json=OPERATION_PAYLOAD
    )

    result = await heidi.delete_passes(TEMPLATE_ID, PERSON_ID)

    assert result.detail == "accepted"


async def test_list_wallet_types(
    heidi: HeidiClient, mock_api: respx.MockRouter
) -> None:
    mock_api.get("/api/v1/wallet_types").respond(json=["APPLE", "GOOGLE"])

    result = await heidi.list_wallet_types()

    assert result == [WalletType.APPLE, WalletType.GOOGLE]


async def test_list_pass_templates(
    heidi: HeidiClient, mock_api: respx.MockRouter
) -> None:
    mock_api.get("/api/v1/pass_templates").respond(
        json=[{"id": TEMPLATE_ID, "title": "Student Card", "wallet_types": ["APPLE"]}]
    )

    result = await heidi.list_pass_templates()

    assert isinstance(result[0], PassTemplate)
    assert result[0].title == "Student Card"


async def test_search_persons_returns_raw_dicts(
    heidi: HeidiClient, mock_api: respx.MockRouter
) -> None:
    mock_api.get(f"/api/v1/search_persons/{TEMPLATE_ID}/ada").respond(
        json=[{"person_id": PERSON_ID, "display_name": "Ada Lovelace"}]
    )

    result = await heidi.search_persons(TEMPLATE_ID, "ada")

    assert result == [{"person_id": PERSON_ID, "display_name": "Ada Lovelace"}]


async def test_person_search_term_is_url_encoded(
    heidi: HeidiClient, mock_api: respx.MockRouter
) -> None:
    route = mock_api.get(
        f"/api/v1/search_persons/{TEMPLATE_ID}/ada%20lovelace"
    ).respond(json=[])

    await heidi.search_persons(TEMPLATE_ID, "ada lovelace")

    assert route.called


async def test_person_search_term_with_slash_is_percent_encoded(
    heidi: HeidiClient, mock_api: respx.MockRouter
) -> None:
    """A ``/`` in the search term must not introduce an extra path segment.

    respx's path matching decodes ``%2F`` back to ``/`` before comparing, so a
    single route (matched by decoded path) catches both an encoded and an
    unencoded request equally. The distinction that matters -- whether the
    slash was actually percent-encoded on the wire -- is only visible on the
    raw request that respx recorded, so that is what this test asserts on.
    """
    route = mock_api.get(f"/api/v1/search_persons/{TEMPLATE_ID}/cs/101").respond(
        json=[]
    )

    await heidi.search_persons(TEMPLATE_ID, "cs/101")

    assert route.called
    sent_path = route.calls[0].request.url.raw_path.decode()
    assert sent_path == f"/api/v1/search_persons/{TEMPLATE_ID}/cs%2F101"


async def test_get_passes_person_id_with_slash_is_percent_encoded(
    heidi: HeidiClient, mock_api: respx.MockRouter
) -> None:
    """A ``/`` in ``person_id`` must not introduce an extra path segment.

    See the search-term counterpart above for why the assertion inspects the
    raw request path rather than relying on respx route dispatch.
    """
    route = mock_api.get(f"/api/v1/passes/{TEMPLATE_ID}/dept/42").respond(
        json=[PASS_PAYLOAD]
    )

    await heidi.get_passes(TEMPLATE_ID, "dept/42")

    assert route.called
    sent_path = route.calls[0].request.url.raw_path.decode()
    assert sent_path == f"/api/v1/passes/{TEMPLATE_ID}/dept%2F42"
