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
    WalletType,
)
from edutap.heidi_api.settings import HeidiSettings

_PASS_LIST = TypeAdapter(list[PassData])
_TEMPLATE_LIST = TypeAdapter(list[PassTemplate])
_WALLET_TYPE_LIST = TypeAdapter(list[WalletType])


class HeidiClient:
    """Flat async client covering the whole HEIDI Cloud API.

    Use it as an async context manager::

        async with HeidiClient() as heidi:
            templates = await heidi.list_pass_templates()
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
        """
        self._settings = settings or HeidiSettings()
        self._owns_http_client = http_client is None
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
    ) -> httpx.Response:
        """Send an authenticated request and raise on error responses.

        A ``401`` answer is treated as an expired token: the token is
        refreshed once and the request replayed. A second ``401`` raises
        :class:`~edutap.heidi_api.exceptions.HeidiAuthError`.
        """
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
        token: str,
        *,
        params: dict[str, str] | None,
        json: object | None,
    ) -> httpx.Response:
        return await self._http_client.request(
            method,
            url,
            params=params,
            json=json,
            headers={"Authorization": f"Bearer {token}"},
        )

    async def whoami(self) -> AuthenticatedUser:
        """Return the user the current access token belongs to."""
        response = await self._request("GET", "/security/authenticated")
        return AuthenticatedUser.model_validate(response.json())

    async def get_pass(self, pass_id: UUID | str) -> PassData:
        """Return a single pass by its identifier."""
        response = await self._request("GET", f"/api/v1/pass/{pass_id}")
        return PassData.model_validate(response.json())

    async def update_pass(self, pass_id: UUID | str) -> PassOperationResponse:
        """Ask HEIDI to update a pass. The update runs asynchronously."""
        response = await self._request("PUT", f"/api/v1/pass/{pass_id}")
        return PassOperationResponse.model_validate(response.json())

    async def delete_pass(self, pass_id: UUID | str) -> PassOperationResponse:
        """Ask HEIDI to delete a pass. The deletion runs asynchronously."""
        response = await self._request("DELETE", f"/api/v1/pass/{pass_id}")
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
            template_id=UUID(str(template_id)),
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
            "GET", f"/api/v1/passes/{template_id}/{quote(person_id)}"
        )
        return _PASS_LIST.validate_python(response.json())

    async def update_passes(
        self, template_id: UUID | str, person_id: str
    ) -> PassOperationResponse:
        """Ask HEIDI to update every pass a person holds for one template."""
        response = await self._request(
            "PUT", f"/api/v1/passes/{template_id}/{quote(person_id)}"
        )
        return PassOperationResponse.model_validate(response.json())

    async def delete_passes(
        self, template_id: UUID | str, person_id: str
    ) -> PassOperationResponse:
        """Ask HEIDI to delete every pass a person holds for one template."""
        response = await self._request(
            "DELETE", f"/api/v1/passes/{template_id}/{quote(person_id)}"
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
            "GET", f"/api/v1/search_persons/{template_id}/{quote(term)}"
        )
        return list(response.json())
