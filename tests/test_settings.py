"""Tests for configuration handling."""

import pytest
from pydantic import SecretStr, ValidationError

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


def test_missing_credentials_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("HEIDI_USERNAME", raising=False)
    monkeypatch.delenv("HEIDI_PASSWORD", raising=False)

    with pytest.raises(ValidationError):
        HeidiSettings(_env_file=None)  # type: ignore


def test_password_is_not_leaked_by_repr() -> None:
    settings = HeidiSettings(username="ada", password=SecretStr("s3cret"))

    assert "s3cret" not in repr(settings)
    assert settings.password.get_secret_value() == "s3cret"
