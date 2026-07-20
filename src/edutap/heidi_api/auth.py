"""Access token lifecycle for the HEIDI client."""

import anyio
import httpx

from edutap.heidi_api.exceptions import HeidiAuthError, error_from_response
from edutap.heidi_api.models import Token
from edutap.heidi_api.settings import HeidiSettings

TOKEN_PATH = "/security/token"  # noqa: S105 -- an endpoint path, not a credential


class TokenManager:
    """Fetches and caches the OAuth2 access token.

    The token carries no expiry, so expiry is detected reactively: the client
    calls :meth:`refresh` after an authenticated request answered ``401``.
    """

    def __init__(self, settings: HeidiSettings, http_client: httpx.AsyncClient) -> None:
        """Store the settings and the shared HTTP client; fetch nothing yet."""
        self._settings = settings
        self._http_client = http_client
        self._token: str | None = None
        self._lock = anyio.Lock()

    async def token(self) -> str:
        """Return the cached token, fetching one on first use."""
        async with self._lock:
            if self._token is None:
                self._token = await self._fetch()
            return self._token

    async def refresh(self, stale_token: str) -> str:
        """Replace ``stale_token`` with a fresh one.

        If another task already replaced it, the newer token is returned
        without a second request.
        """
        async with self._lock:
            if self._token == stale_token or self._token is None:
                self._token = await self._fetch()
            return self._token

    async def _fetch(self) -> str:
        """Perform the OAuth2 password grant.

        :raises HeidiAuthError: if ``username`` or ``password`` is not
            configured. Settings built for pure self-service use
            (:meth:`~edutap.heidi_api.client.HeidiClient.get_self_service_info`,
            :meth:`~edutap.heidi_api.client.HeidiClient.create_pass_from_payload`)
            carry no credentials, so this is raised instead of sending a
            request with ``None`` values.
        """
        if self._settings.username is None or self._settings.password is None:
            raise HeidiAuthError(
                "Cannot obtain an access token: HEIDI_USERNAME and "
                "HEIDI_PASSWORD are not configured. Set them, or use only "
                "the unauthenticated self-service methods "
                "(get_self_service_info, create_pass_from_payload)."
            )
        response = await self._http_client.post(
            TOKEN_PATH,
            data={
                "grant_type": "password",
                "username": self._settings.username,
                "password": self._settings.password.get_secret_value(),
            },
        )
        error = error_from_response(response)
        if error is not None:
            raise error
        return Token.model_validate(response.json()).access_token
