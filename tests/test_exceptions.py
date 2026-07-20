"""Tests for the exception hierarchy and the response mapper."""

import httpx
import pytest

from edutap.heidi_api.exceptions import (
    HeidiAuthError,
    HeidiConflictError,
    HeidiError,
    HeidiNotFoundError,
    HeidiRateLimitError,
    HeidiServerError,
    HeidiValidationError,
    error_from_response,
)


def _response(
    status_code: int,
    *,
    json: object = None,
    text: str | None = None,
    headers: dict[str, str] | None = None,
    url: str = "https://api.example.org/api/v1/pass",
    method: str = "GET",
) -> httpx.Response:
    request = httpx.Request(method, url)
    return httpx.Response(
        status_code, request=request, json=json, text=text, headers=headers
    )


def test_success_maps_to_no_error() -> None:
    assert error_from_response(_response(200)) is None
    assert error_from_response(_response(202)) is None


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (401, HeidiAuthError),
        (404, HeidiNotFoundError),
        (409, HeidiConflictError),
        (422, HeidiValidationError),
        (429, HeidiRateLimitError),
        (500, HeidiServerError),
        (503, HeidiServerError),
    ],
)
def test_status_codes_map_to_their_exception(
    status_code: int, expected: type[HeidiError]
) -> None:
    error = error_from_response(_response(status_code))

    assert isinstance(error, expected)
    assert error.status_code == status_code
    assert error.request_url == "https://api.example.org/api/v1/pass"


def test_unmapped_client_error_maps_to_the_base_error() -> None:
    error = error_from_response(_response(418))

    assert type(error) is HeidiError
    assert error.status_code == 418


def test_every_error_is_a_heidi_error() -> None:
    for status_code in (401, 404, 409, 422, 429, 500):
        assert isinstance(error_from_response(_response(status_code)), HeidiError)


def test_validation_error_exposes_parsed_details() -> None:
    error = error_from_response(
        _response(
            422,
            json={
                "detail": [
                    {
                        "loc": ["body", "person_id"],
                        "msg": "field required",
                        "type": "missing",
                    }
                ]
            },
        )
    )

    assert isinstance(error, HeidiValidationError)
    assert error.errors[0].msg == "field required"
    assert error.errors[0].loc == ["body", "person_id"]


def test_validation_error_survives_an_unparsable_body() -> None:
    error = error_from_response(_response(422, text="not json"))

    assert isinstance(error, HeidiValidationError)
    assert error.errors == []


def test_rate_limit_error_reads_retry_after() -> None:
    error = error_from_response(_response(429, headers={"Retry-After": "12"}))

    assert isinstance(error, HeidiRateLimitError)
    assert error.retry_after == 12.0


def test_rate_limit_error_without_header() -> None:
    error = error_from_response(_response(429))

    assert isinstance(error, HeidiRateLimitError)
    assert error.retry_after is None


def test_error_keeps_the_response_body() -> None:
    error = error_from_response(_response(404, text="pass not found"))

    assert error is not None
    assert error.body == "pass not found"
    assert "404" in str(error)


def test_error_redacts_the_query_string_of_the_request_url() -> None:
    """The self-service calls carry the opaque payload as a query parameter.

    It must not end up verbatim in an exception's message or ``request_url``
    -- both are prone to landing in logs.
    """
    error = error_from_response(
        _response(
            401,
            text="unauthorized",
            url="https://api.example.org/api/v1/self-service/info"
            "?payload=super-secret-token",
            method="POST",
        )
    )

    assert error is not None
    assert error.request_url is not None
    assert "super-secret-token" not in str(error)
    assert "super-secret-token" not in error.request_url
    assert error.request_url == (
        "https://api.example.org/api/v1/self-service/info?<redacted>"
    )


def test_error_request_url_is_unchanged_without_a_query_string() -> None:
    error = error_from_response(_response(404, text="pass not found"))

    assert error is not None
    assert error.request_url == "https://api.example.org/api/v1/pass"
    assert "?" not in error.request_url
