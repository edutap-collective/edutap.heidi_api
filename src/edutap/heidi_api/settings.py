"""Configuration for the HEIDI client."""

from pydantic import HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class HeidiSettings(BaseSettings):
    """Connection settings, read from the environment by default.

    Environment variables use the prefix ``HEIDI_``, for example
    ``HEIDI_USERNAME`` and ``HEIDI_PASSWORD``.

    ``username`` and ``password`` are optional: they are only needed for
    the issuer operations and for :meth:`HeidiClient.get_self_service_payload`.
    ``HeidiClient.get_self_service_info`` and
    ``HeidiClient.create_pass_from_payload`` carry no security requirement
    upstream and work with a client built from settings that have no
    credentials at all -- see :class:`~edutap.heidi_api.auth.TokenManager`
    for what happens if a token is requested without them.
    """

    model_config = SettingsConfigDict(
        env_prefix="HEIDI_",
        env_file=".env",
        extra="ignore",
    )

    base_url: HttpUrl = HttpUrl("https://api.cloud.heidi-pass.com")
    username: str | None = None
    password: SecretStr | None = None
    timeout: float = 30.0
