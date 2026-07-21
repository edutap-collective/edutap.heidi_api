"""Tests for the standalone id-validation helpers."""

import re
from uuid import UUID

import pytest

from edutap.heidi_api.validation import to_uuid_segment, validate_person_id

VALID_UUID = UUID("11111111-1111-1111-1111-111111111111")
VALID_UUID_STR = "11111111-1111-1111-1111-111111111111"


def test_to_uuid_segment_round_trips_a_uuid_object() -> None:
    assert to_uuid_segment(VALID_UUID, "pass_id") == VALID_UUID_STR


def test_to_uuid_segment_round_trips_a_canonical_uuid_string() -> None:
    assert to_uuid_segment(VALID_UUID_STR, "pass_id") == VALID_UUID_STR


def test_to_uuid_segment_rejects_a_non_uuid_string_naming_the_param() -> None:
    bad_id = "../../security/authenticated"

    with pytest.raises(ValueError, match=f"pass_id.*{re.escape(bad_id)}"):
        to_uuid_segment(bad_id, "pass_id")


@pytest.mark.parametrize(
    "person_id",
    [
        "jdoe@example.edu",  # eduPersonPrincipalName-style
        "user123@idp.example.org",  # eduPersonUniqueId-style
        "aB=cd-1234@example.edu",  # subject-id/pairwise-id-style, base64url charset
        f"{'a' * 256}@example.edu",  # local part at the 256-char boundary
    ],
)
def test_validate_person_id_accepts_scoped_identifiers(person_id: str) -> None:
    assert validate_person_id(person_id) == person_id


@pytest.mark.parametrize(
    "person_id",
    [
        "person-42",  # no scope at all
        "jdoe/admin@example.edu",  # contains a slash
        "jdoe doe@example.edu",  # contains whitespace
        "",  # empty
        f"{'a' * 257}@example.edu",  # local part exceeds 256 chars
        "jdoe\x00@example.edu",  # control character
    ],
)
def test_validate_person_id_rejects_invalid_values(person_id: str) -> None:
    with pytest.raises(ValueError, match="person_id"):
        validate_person_id(person_id)
