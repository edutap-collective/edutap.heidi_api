"""Tests for the self-service endpoints."""

import pytest
import respx

from edutap.heidi_api.client import HeidiClient
from edutap.heidi_api.models import PassState, PayloadInfo, WalletType

pytestmark = pytest.mark.anyio

TEMPLATE_ID = "22222222-2222-2222-2222-222222222222"
PERSON_ID = "person-42"
PAYLOAD = "opaque-payload-token"


async def test_get_self_service_payload_returns_the_raw_payload(
    heidi: HeidiClient, mock_api: respx.MockRouter
) -> None:
    mock_api.get(f"/api/v1/self-service/payload/{TEMPLATE_ID}/{PERSON_ID}").respond(
        text=PAYLOAD
    )

    result = await heidi.get_self_service_payload(TEMPLATE_ID, PERSON_ID)

    assert result == PAYLOAD


async def test_get_self_service_payload_person_id_with_slash_is_percent_encoded(
    heidi: HeidiClient, mock_api: respx.MockRouter
) -> None:
    """A ``/`` in ``person_id`` must not introduce an extra path segment.

    See the search-term counterpart in ``test_client_issuer.py`` for why the
    assertion inspects the raw request path rather than relying on respx
    route dispatch: respx decodes ``%2F`` back to ``/`` before matching, so
    only the raw recorded path reveals whether the slash was actually
    percent-encoded on the wire.
    """
    route = mock_api.get(f"/api/v1/self-service/payload/{TEMPLATE_ID}/dept/42").respond(
        text=PAYLOAD
    )

    await heidi.get_self_service_payload(TEMPLATE_ID, "dept/42")

    assert route.called
    sent_path = route.calls[0].request.url.raw_path.decode()
    assert sent_path == f"/api/v1/self-service/payload/{TEMPLATE_ID}/dept%2F42"


async def test_get_self_service_info_sends_the_payload_as_a_query_parameter(
    heidi: HeidiClient, mock_api: respx.MockRouter
) -> None:
    route = mock_api.post("/api/v1/self-service/info").respond(
        json={
            "template_display_name": "Student Card",
            "wallet_types": ["APPLE"],
            "passes": [
                {"wallet_type": "APPLE", "pass_state": "Active", "install_link": None}
            ],
        }
    )

    result = await heidi.get_self_service_info(PAYLOAD)

    assert isinstance(result, PayloadInfo)
    assert result.template_display_name == "Student Card"
    assert result.passes[0].pass_state is PassState.ACTIVE
    assert route.calls[0].request.url.params["payload"] == PAYLOAD
    assert route.calls[0].request.content == b""


async def test_create_pass_from_payload(
    heidi: HeidiClient, mock_api: respx.MockRouter
) -> None:
    route = mock_api.post("/api/v1/self-service/create/APPLE").respond(
        202,
        json={"pass_id": "11111111-1111-1111-1111-111111111111", "detail": "accepted"},
    )

    result = await heidi.create_pass_from_payload(WalletType.APPLE, PAYLOAD)

    assert result.detail == "accepted"
    assert route.calls[0].request.url.params["payload"] == PAYLOAD


async def test_create_pass_from_payload_accepts_a_string_wallet_type(
    heidi: HeidiClient, mock_api: respx.MockRouter
) -> None:
    route = mock_api.post("/api/v1/self-service/create/GOOGLE").respond(
        202,
        json={"pass_id": "11111111-1111-1111-1111-111111111111", "detail": "accepted"},
    )

    await heidi.create_pass_from_payload("GOOGLE", PAYLOAD)

    assert route.called
