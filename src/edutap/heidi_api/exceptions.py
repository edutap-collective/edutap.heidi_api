"""Exceptions raised by the HEIDI client."""

import httpx
from pydantic import ValidationError as PydanticValidationError

from edutap.heidi_api.models import ValidationErrorDetail


class HeidiError(Exception):
    """Base class for every error answer of the HEIDI API."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        request_url: str | None = None,
        body: str | None = None,
    ) -> None:
        """Store the error message and the response context it came from."""
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.request_url = request_url
        self.body = body


class HeidiAuthError(HeidiError):
    """Authentication failed or the access token is not accepted (401)."""


class HeidiNotFoundError(HeidiError):
    """The requested pass, template or person does not exist (404)."""


class HeidiConflictError(HeidiError):
    """The pass is busy with another operation (409)."""


class HeidiValidationError(HeidiError):
    """The request was rejected as invalid (422)."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        request_url: str | None = None,
        body: str | None = None,
        errors: list[ValidationErrorDetail] | None = None,
    ) -> None:
        """Store the error message plus the parsed validation error details."""
        super().__init__(
            message, status_code=status_code, request_url=request_url, body=body
        )
        self.errors = errors or []


class HeidiRateLimitError(HeidiError):
    """Too many requests (429)."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        request_url: str | None = None,
        body: str | None = None,
        retry_after: float | None = None,
    ) -> None:
        """Store the error message plus the parsed ``Retry-After`` value."""
        super().__init__(
            message, status_code=status_code, request_url=request_url, body=body
        )
        self.retry_after = retry_after


class HeidiServerError(HeidiError):
    """The HEIDI service failed to handle the request (5xx)."""


_STATUS_MAP: dict[int, type[HeidiError]] = {
    401: HeidiAuthError,
    404: HeidiNotFoundError,
    409: HeidiConflictError,
}


def _validation_details(response: httpx.Response) -> list[ValidationErrorDetail]:
    """Parse the ``detail`` list of a FastAPI validation error response."""
    try:
        payload = response.json()
    except ValueError:
        return []
    if not isinstance(payload, dict):
        return []
    try:
        return [
            ValidationErrorDetail.model_validate(entry)
            for entry in payload.get("detail", [])
        ]
    except (PydanticValidationError, TypeError):
        return []


def _retry_after(response: httpx.Response) -> float | None:
    """Read the ``Retry-After`` header as seconds, if it is a number."""
    raw = response.headers.get("Retry-After")
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _redacted_url(url: httpx.URL) -> str:
    """Return ``url`` with its query string replaced by a redaction marker.

    The self-service endpoints carry the opaque payload -- a capability-like
    secret -- as a query parameter. Keeping it out of exception messages
    keeps it out of logs too. The path and everything before it is kept
    unchanged since it carries no secret.
    """
    without_query = str(url.copy_with(query=None))
    return f"{without_query}?<redacted>" if url.query else without_query


def error_from_response(response: httpx.Response) -> HeidiError | None:
    """Map an HTTP response to a :class:`HeidiError`, or ``None`` if it is fine."""
    if response.status_code < 400:
        return None

    request_url = _redacted_url(response.request.url)
    message = f"HEIDI API returned {response.status_code} for {request_url}"
    status_code = response.status_code
    body = response.text

    if status_code == 422:
        return HeidiValidationError(
            message,
            status_code=status_code,
            request_url=request_url,
            body=body,
            errors=_validation_details(response),
        )
    if status_code == 429:
        return HeidiRateLimitError(
            message,
            status_code=status_code,
            request_url=request_url,
            body=body,
            retry_after=_retry_after(response),
        )
    if status_code >= 500:
        return HeidiServerError(
            message, status_code=status_code, request_url=request_url, body=body
        )
    error_class = _STATUS_MAP.get(status_code, HeidiError)
    return error_class(
        message, status_code=status_code, request_url=request_url, body=body
    )
