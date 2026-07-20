"""Async client for the HEIDI Cloud Service API."""

from types import TracebackType
from typing import Self

import httpx

from edutap.heidi_api.auth import TokenManager
from edutap.heidi_api.exceptions import error_from_response
from edutap.heidi_api.models import AuthenticatedUser
from edutap.heidi_api.settings import HeidiSettings


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
