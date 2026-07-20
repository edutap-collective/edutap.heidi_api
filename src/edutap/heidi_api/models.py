"""Pydantic models mirroring the HEIDI Cloud API wire format."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel


class WalletType(StrEnum):
    """Wallet ecosystem a pass belongs to."""

    UNSET = "UNSET"
    APPLE = "APPLE"
    GOOGLE = "GOOGLE"


class PassState(StrEnum):
    """Lifecycle state of a pass, as reported by HEIDI.

    The values keep the API spelling, including spaces.
    """

    NEW = "New"
    INSTALL_PENDING = "Install pending"
    UPDATE_PENDING = "Update pending"
    DELETE_PENDING = "Delete pending"
    ACTIVE = "Active"
    INACTIVE = "Inactive"


class PassData(BaseModel):
    """A single pass belonging to a person and a template."""

    pass_id: UUID
    person_id: str
    template_id: UUID
    wallet_type: WalletType
    pass_state: PassState
    last_update: datetime
    install_link: str | None = None


class PassTemplate(BaseModel):
    """A pass template offered by the customer's HEIDI installation."""

    id: UUID
    title: str
    wallet_types: list[WalletType]


class PayloadPass(BaseModel):
    """Pass information contained in a self-service payload."""

    wallet_type: WalletType
    pass_state: PassState
    install_link: str | None = None


class PayloadInfo(BaseModel):
    """Description of what a self-service payload refers to."""

    template_display_name: str
    wallet_types: list[WalletType] = []
    passes: list[PayloadPass] = []


class PassOperationResponse(BaseModel):
    """Acknowledgement of an asynchronous pass operation."""

    pass_id: UUID
    detail: str


class Token(BaseModel):
    """OAuth2 access token as returned by ``POST /security/token``."""

    access_token: str
    token_type: str


class AuthenticatedUser(BaseModel):
    """The user behind the current access token."""

    display_name: str
    username: str
    roles: list[str]
    customer_id: UUID | None = None
    customer_display_name: str | None = None


class ValidationErrorDetail(BaseModel):
    """One entry of a FastAPI ``422`` validation error response."""

    loc: list[str | int]
    msg: str
    type: str


class CreatePassOperation(BaseModel):
    """Request body of ``POST /api/v1/pass``."""

    wallet_type: WalletType
    template_id: UUID
    person_id: str
