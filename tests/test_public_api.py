"""The public import surface of the package."""

import edutap.heidi_api as package

EXPECTED = {
    "AuthenticatedUser",
    "HeidiAuthError",
    "HeidiClient",
    "HeidiConflictError",
    "HeidiError",
    "HeidiNotFoundError",
    "HeidiRateLimitError",
    "HeidiServerError",
    "HeidiSettings",
    "HeidiValidationError",
    "PassData",
    "PassOperationResponse",
    "PassState",
    "PassTemplate",
    "PayloadInfo",
    "PayloadPass",
    "ValidationErrorDetail",
    "WalletType",
    "__version__",
}


def test_public_names_are_exported() -> None:
    assert set(package.__all__) == EXPECTED


def test_every_exported_name_is_importable() -> None:
    for name in package.__all__:
        assert getattr(package, name) is not None


def test_client_is_importable_from_the_package_root() -> None:
    from edutap.heidi_api import HeidiClient

    assert HeidiClient.__name__ == "HeidiClient"
