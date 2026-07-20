"""Configuration for the HEIDI client."""

from pydantic import HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class HeidiSettings(BaseSettings):
    """Connection settings, read from the environment by default.

    Environment variables use the prefix ``HEIDI_``, for example
    ``HEIDI_USERNAME`` and ``HEIDI_PASSWORD``.
    """

    model_config = SettingsConfigDict(
        env_prefix="HEIDI_",
        env_file=".env",
        extra="ignore",
    )

    base_url: HttpUrl = HttpUrl("https://api.cloud.heidi-pass.com")
    username: str
    password: SecretStr
    timeout: float = 30.0
