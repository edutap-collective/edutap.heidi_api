"""Pythonic async client for the HEIDI Cloud Service API."""

from importlib.metadata import version

from edutap.heidi_api.client import HeidiClient
from edutap.heidi_api.exceptions import (
    HeidiAuthError,
    HeidiConflictError,
    HeidiError,
    HeidiNotFoundError,
    HeidiRateLimitError,
    HeidiServerError,
    HeidiValidationError,
)
from edutap.heidi_api.models import (
    AuthenticatedUser,
    PassData,
    PassOperationResponse,
    PassState,
    PassTemplate,
    PayloadInfo,
    PayloadPass,
    WalletType,
)
from edutap.heidi_api.settings import HeidiSettings

__version__ = version("edutap.heidi_api")

__all__ = [
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
    "WalletType",
    "__version__",
]
