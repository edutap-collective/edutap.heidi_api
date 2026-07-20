"""Async client for the HEIDI Cloud Service API."""

from types import TracebackType
from typing import Any, Self
from urllib.parse import quote
from uuid import UUID

import httpx
from pydantic import TypeAdapter

from edutap.heidi_api.auth import TokenManager
from edutap.heidi_api.exceptions import error_from_response
from edutap.heidi_api.models import (
    AuthenticatedUser,
    CreatePassOperation,
    PassData,
    PassOperationResponse,
    PassTemplate,
    PayloadInfo,
    WalletType,
)
from edutap.heidi_api.settings import HeidiSettings

_PASS_LIST = TypeAdapter(list[PassData])
_TEMPLATE_LIST = TypeAdapter(list[PassTemplate])
_WALLET_TYPE_LIST = TypeAdapter(list[WalletType])
_PERSON_LIST = TypeAdapter(list[dict[str, Any]])


def _uuid_segment(value: UUID | str, param_name: str) -> str:
    """Validate an identifier and render it as a safe path segment.

    The upstream spec declares ``pass_id`` and ``template_id`` as
    ``format: uuid``. Rejecting anything else keeps a caller-supplied value
    from being interpreted as a path-traversal (``../``) or query-injection
    (``?...``) segment once it is spliced into a URL.

    :param param_name: name of the caller-facing argument ``value`` came
        from, used to name it in the error message.
    :raises ValueError: if ``value`` is not a valid UUID.
    """
    try:
        return str(UUID(str(value)))
    except ValueError as exc:
        raise ValueError(f"{param_name} is not a valid UUID: {value!r}") from exc


class HeidiClient:
    """Flat async client covering the whole HEIDI Cloud API.

    Use it as an async context manager::

        async with HeidiClient() as heidi:
            templates = await heidi.list_pass_templates()

    Every request is sent as a URL relative to ``settings.base_url``. An
    injected ``http_client`` (see :meth:`__init__`) must therefore already
    carry a ``base_url`` of its own -- ``HeidiClient`` raises ``ValueError``
    at construction time otherwise, rather than failing later with an
    opaque ``httpx`` error.
    """

    def __init__(
        self,
        settings: HeidiSettings | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        """Set up settings, HTTP transport and token manager.

        A ``http_client`` passed in is borrowed, not owned: :meth:`aclose`
        leaves it open for the caller to reuse or close. Without one, the
        client creates and owns its own ``httpx.AsyncClient``.

        Every request is sent as a relative URL, so an injected
        ``http_client`` must already carry a ``base_url`` -- typically
        ``settings.base_url``. ``settings.timeout`` is only applied to a
        client this method creates itself; an injected client keeps its own
        timeout.

        :raises ValueError: if ``http_client`` is given but has no
            ``base_url`` configured.
        """
        self._settings = settings or HeidiSettings()
        self._owns_http_client = http_client is None
        if http_client is not None and not str(http_client.base_url):
            raise ValueError(
                "http_client must be created with a base_url, e.g. "
                "httpx.AsyncClient(base_url=settings.base_url); HeidiClient "
                "sends every request as a relative URL."
            )
        self._http_client = http_client or httpx.AsyncClient(
            base_url=str(self._settings.base_url),
            timeout=self._settings.timeout,
        )
        self._tokens = TokenManager(self._settings, self._http_client)

    async def __aenter__(self) -> Self:
        """Return ``self`` unchanged; setup already happened in ``__init__``."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the client on context-manager exit."""
        await self.aclose()

    async def aclose(self) -> None:
        """Close the underlying HTTP client, unless it was injected."""
        if self._owns_http_client:
            await self._http_client.aclose()

    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, str] | None = None,
        json: object | None = None,
        authenticated: bool = True,
    ) -> httpx.Response:
        """Send a request and raise on error responses.

        A ``401`` answer on an ``authenticated`` request is treated as an
        expired token: the token is refreshed once and the request
        replayed. A second ``401`` raises
        :class:`~edutap.heidi_api.exceptions.HeidiAuthError`.

        When ``authenticated`` is ``False``, no token is fetched and no
        ``Authorization`` header is sent -- use this for the self-service
        operations that carry no security requirement upstream, where the
        opaque payload is itself the authorization. A ``401`` there is not
        retried; it maps to :class:`~edutap.heidi_api.exceptions.HeidiAuthError`
        like any other error status.
        """
        if not authenticated:
            response = await self._send(method, url, None, params=params, json=json)
            error = error_from_response(response)
            if error is not None:
                raise error
            return response

        token = await self._tokens.token()
        response = await self._send(method, url, token, params=params, json=json)

        if response.status_code == httpx.codes.UNAUTHORIZED:
            token = await self._tokens.refresh(token)
            response = await self._send(method, url, token, params=params, json=json)

        error = error_from_response(response)
        if error is not None:
            raise error
        return response

    async def _send(
        self,
        method: str,
        url: str,
        token: str | None,
        *,
        params: dict[str, str] | None,
        json: object | None,
    ) -> httpx.Response:
        headers = {"Authorization": f"Bearer {token}"} if token is not None else None
        return await self._http_client.request(
            method,
            url,
            params=params,
            json=json,
            headers=headers,
        )

    async def whoami(self) -> AuthenticatedUser:
        """Return the user the current access token belongs to."""
        response = await self._request("GET", "/security/authenticated")
        return AuthenticatedUser.model_validate(response.json())

    async def get_pass(self, pass_id: UUID | str) -> PassData:
        """Return a single pass by its identifier."""
        response = await self._request(
            "GET", f"/api/v1/pass/{_uuid_segment(pass_id, 'pass_id')}"
        )
        return PassData.model_validate(response.json())

    async def update_pass(self, pass_id: UUID | str) -> PassOperationResponse:
        """Ask HEIDI to update a pass. The update runs asynchronously."""
        response = await self._request(
            "PUT", f"/api/v1/pass/{_uuid_segment(pass_id, 'pass_id')}"
        )
        return PassOperationResponse.model_validate(response.json())

    async def delete_pass(self, pass_id: UUID | str) -> PassOperationResponse:
        """Ask HEIDI to delete a pass. The deletion runs asynchronously."""
        response = await self._request(
            "DELETE", f"/api/v1/pass/{_uuid_segment(pass_id, 'pass_id')}"
        )
        return PassOperationResponse.model_validate(response.json())

    async def create_pass(
        self,
        *,
        template_id: UUID | str,
        person_id: str,
        wallet_type: WalletType | str,
    ) -> PassOperationResponse:
        """Ask HEIDI to create a pass for a person from a template."""
        operation = CreatePassOperation(
            wallet_type=WalletType(wallet_type),
            template_id=_uuid_segment(template_id, "template_id"),
            person_id=person_id,
        )
        response = await self._request(
            "POST", "/api/v1/pass", json=operation.model_dump(mode="json")
        )
        return PassOperationResponse.model_validate(response.json())

    async def get_passes(
        self, template_id: UUID | str, person_id: str
    ) -> list[PassData]:
        """Return every pass a person holds for one template."""
        response = await self._request(
            "GET",
            f"/api/v1/passes/{_uuid_segment(template_id, 'template_id')}/"
            f"{quote(person_id, safe='')}",
        )
        return _PASS_LIST.validate_python(response.json())

    async def update_passes(
        self, template_id: UUID | str, person_id: str
    ) -> PassOperationResponse:
        """Ask HEIDI to update every pass a person holds for one template."""
        response = await self._request(
            "PUT",
            f"/api/v1/passes/{_uuid_segment(template_id, 'template_id')}/"
            f"{quote(person_id, safe='')}",
        )
        return PassOperationResponse.model_validate(response.json())

    async def delete_passes(
        self, template_id: UUID | str, person_id: str
    ) -> PassOperationResponse:
        """Ask HEIDI to delete every pass a person holds for one template."""
        response = await self._request(
            "DELETE",
            f"/api/v1/passes/{_uuid_segment(template_id, 'template_id')}/"
            f"{quote(person_id, safe='')}",
        )
        return PassOperationResponse.model_validate(response.json())

    async def list_wallet_types(self) -> list[WalletType]:
        """Return the wallet types this installation supports."""
        response = await self._request("GET", "/api/v1/wallet_types")
        return _WALLET_TYPE_LIST.validate_python(response.json())

    async def list_pass_templates(self) -> list[PassTemplate]:
        """Return the pass templates available to the authenticated customer."""
        response = await self._request("GET", "/api/v1/pass_templates")
        return _TEMPLATE_LIST.validate_python(response.json())

    async def search_persons(
        self, template_id: UUID | str, term: str
    ) -> list[dict[str, Any]]:
        """Search persons eligible for a template.

        The API declares free-form objects here, so the raw dictionaries are
        returned unchanged.
        """
        response = await self._request(
            "GET",
            f"/api/v1/search_persons/"
            f"{_uuid_segment(template_id, 'template_id')}/{quote(term, safe='')}",
        )
        return _PERSON_LIST.validate_python(response.json())

    async def get_self_service_payload(
        self, template_id: UUID | str, person_id: str
    ) -> str:
        """Return the opaque self-service payload for a person and template.

        The payload has no documented structure; pass it back unchanged to
        :meth:`get_self_service_info` or :meth:`create_pass_from_payload`.

        This call is authenticated, unlike its two self-service siblings.

        The spec declares this response as ``application/json`` with
        ``type: string``, so the body may arrive JSON-encoded (quoted) rather
        than as raw text. Both shapes are normalised to the plain string.

        Upstream actually declares ``type: string, format: binary``, so a
        server may also answer with a ``content-type: application/json``
        header and a body that is not valid JSON at all (e.g. base64 bytes).
        That case falls back to the raw text exactly like a non-JSON
        content type, rather than raising ``JSONDecodeError``.
        """
        response = await self._request(
            "GET",
            f"/api/v1/self-service/payload/"
            f"{_uuid_segment(template_id, 'template_id')}/"
            f"{quote(person_id, safe='')}",
        )
        content_type = response.headers.get("content-type", "")
        if content_type.startswith("application/json"):
            try:
                decoded = response.json()
            except ValueError:
                return response.text
            if isinstance(decoded, str):
                return decoded
        return response.text

    async def get_self_service_info(self, payload: str) -> PayloadInfo:
        """Describe what a self-service payload refers to.

        Unauthenticated: the spec declares no security requirement for this
        operation, so no issuer credentials are needed and none are sent.
        The opaque payload is itself the authorization.
        """
        response = await self._request(
            "POST",
            "/api/v1/self-service/info",
            params={"payload": payload},
            authenticated=False,
        )
        return PayloadInfo.model_validate(response.json())

    async def create_pass_from_payload(
        self, wallet_type: WalletType | str, payload: str
    ) -> PassOperationResponse:
        """Create a pass for the person a self-service payload refers to.

        Unauthenticated: the spec declares no security requirement for this
        operation, so no issuer credentials are needed and none are sent.
        The opaque payload is itself the authorization.
        """
        response = await self._request(
            "POST",
            f"/api/v1/self-service/create/{WalletType(wallet_type).value}",
            params={"payload": payload},
            authenticated=False,
        )
        return PassOperationResponse.model_validate(response.json())
