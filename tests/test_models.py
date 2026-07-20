"""Tests for the wire-format models."""

from datetime import datetime
from uuid import UUID

from edutap.heidi_api.models import (
    AuthenticatedUser,
    CreatePassOperation,
    PassData,
    PassOperationResponse,
    PassState,
    PassTemplate,
    PayloadInfo,
    Token,
    ValidationErrorDetail,
    WalletType,
)


def test_wallet_type_values() -> None:
    assert [member.value for member in WalletType] == ["UNSET", "APPLE", "GOOGLE"]


def test_pass_state_keeps_the_api_spelling() -> None:
    assert PassState.INSTALL_PENDING.value == "Install pending"
    assert PassState("Delete pending") is PassState.DELETE_PENDING


def test_pass_data_parses_an_api_response() -> None:
    data = PassData.model_validate(
        {
            "pass_id": "11111111-1111-1111-1111-111111111111",
            "person_id": "person-42",
            "template_id": "22222222-2222-2222-2222-222222222222",
            "wallet_type": "APPLE",
            "pass_state": "Install pending",
            "last_update": "2026-07-20T10:11:12Z",
            "install_link": None,
        }
    )

    assert data.pass_id == UUID("11111111-1111-1111-1111-111111111111")
    assert data.wallet_type is WalletType.APPLE
    assert data.pass_state is PassState.INSTALL_PENDING
    assert isinstance(data.last_update, datetime)
    assert data.install_link is None


def test_pass_template_parses_wallet_types() -> None:
    template = PassTemplate.model_validate(
        {
            "id": "22222222-2222-2222-2222-222222222222",
            "title": "Student Card",
            "wallet_types": ["APPLE", "GOOGLE"],
        }
    )

    assert template.title == "Student Card"
    assert template.wallet_types == [WalletType.APPLE, WalletType.GOOGLE]


def test_payload_info_defaults_to_empty_collections() -> None:
    info = PayloadInfo.model_validate({"template_display_name": "Student Card"})

    assert info.wallet_types == []
    assert info.passes == []


def test_payload_info_parses_nested_passes() -> None:
    info = PayloadInfo.model_validate(
        {
            "template_display_name": "Student Card",
            "wallet_types": ["GOOGLE"],
            "passes": [
                {
                    "wallet_type": "GOOGLE",
                    "pass_state": "Active",
                    "install_link": "https://example.org/i",
                }
            ],
        }
    )

    assert info.passes[0].pass_state is PassState.ACTIVE
    assert info.passes[0].install_link == "https://example.org/i"


def test_pass_operation_response_parses() -> None:
    response = PassOperationResponse.model_validate(
        {"pass_id": "11111111-1111-1111-1111-111111111111", "detail": "accepted"}
    )

    assert response.detail == "accepted"


def test_token_parses() -> None:
    token = Token.model_validate({"access_token": "abc", "token_type": "bearer"})

    assert token.access_token == "abc"  # noqa: S105


def test_authenticated_user_allows_missing_customer() -> None:
    user = AuthenticatedUser.model_validate(
        {
            "display_name": "Ada Lovelace",
            "username": "ada",
            "roles": ["issuer"],
            "customer_id": None,
            "customer_display_name": None,
        }
    )

    assert user.roles == ["issuer"]
    assert user.customer_id is None


def test_validation_error_detail_parses_mixed_location() -> None:
    detail = ValidationErrorDetail.model_validate(
        {"loc": ["body", 0, "person_id"], "msg": "field required", "type": "missing"}
    )

    assert detail.loc == ["body", 0, "person_id"]


def test_create_pass_operation_serialises_enum_as_string() -> None:
    operation = CreatePassOperation(
        wallet_type=WalletType.APPLE,
        template_id=UUID("22222222-2222-2222-2222-222222222222"),
        person_id="person-42",
    )

    assert operation.model_dump(mode="json") == {
        "wallet_type": "APPLE",
        "template_id": "22222222-2222-2222-2222-222222222222",
        "person_id": "person-42",
    }
