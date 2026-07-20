"""Tests for configuration handling."""

import pytest
from pydantic import SecretStr

from edutap.heidi_api.settings import HeidiSettings


def test_settings_read_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HEIDI_USERNAME", "ada")
    monkeypatch.setenv("HEIDI_PASSWORD", "s3cret")

    settings = HeidiSettings()

    assert settings.username == "ada"
    assert settings.password == SecretStr("s3cret")
    assert str(settings.base_url) == "https://api.cloud.heidi-pass.com/"
    assert settings.timeout == 30.0


def test_base_url_and_timeout_are_overridable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HEIDI_USERNAME", "ada")
    monkeypatch.setenv("HEIDI_PASSWORD", "s3cret")
    monkeypatch.setenv("HEIDI_BASE_URL", "https://staging.example.org")
    monkeypatch.setenv("HEIDI_TIMEOUT", "5")

    settings = HeidiSettings()

    assert str(settings.base_url) == "https://staging.example.org/"
    assert settings.timeout == 5.0


def test_credentials_are_optional_for_pure_self_service_use(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A client built for pure self-service use needs no credentials.

    ``get_self_service_info`` and ``create_pass_from_payload`` carry no
    security requirement upstream, so settings must be constructible
    without ``HEIDI_USERNAME``/``HEIDI_PASSWORD``. Anything that does need
    a token raises :class:`HeidiAuthError` lazily, when a token is actually
    requested; see ``tests/test_auth.py``.
    """
    monkeypatch.delenv("HEIDI_USERNAME", raising=False)
    monkeypatch.delenv("HEIDI_PASSWORD", raising=False)

    settings = HeidiSettings(_env_file=None)  # type: ignore

    assert settings.username is None
    assert settings.password is None


def test_password_is_not_leaked_by_repr() -> None:
    settings = HeidiSettings(username="ada", password=SecretStr("s3cret"))

    assert "s3cret" not in repr(settings)
    assert settings.password is not None
    assert settings.password.get_secret_value() == "s3cret"
