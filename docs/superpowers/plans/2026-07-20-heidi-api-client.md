# HEIDI Cloud API Client Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `edutap.heidi_api`, an async Python client library for the HEIDI Cloud Service (<https://api.cloud.heidi-pass.com>).

**Architecture:** A namespace package under `src/edutap/heidi_api/` with one responsibility per module: `settings` (configuration), `models` (wire contract), `exceptions` (error surface), `auth` (token lifecycle), `client` (transport plus a flat set of endpoint methods). Every HTTP call funnels through one private `_request()` helper that attaches the bearer token, re-authenticates once on `401`, and maps error statuses to typed exceptions.

**Tech Stack:** Python 3.12+, httpx (AsyncClient), Pydantic v2, pydantic-settings, anyio, pytest + anyio + respx, ruff, ty, uv, tox, prek.

Design spec: `docs/superpowers/specs/2026-07-20-heidi-api-client-design.md`

## Global Constraints

- Package name `edutap.heidi_api`, PEP 420 namespace package, `src/` layout. No `__init__.py` in `src/edutap/`.
- Python 3.12+. Test matrix: 3.12, 3.13, 3.14.
- Async only. Every public method is `async def`. No sync facade.
- Runtime dependencies limited to `httpx`, `pydantic`, `pydantic-settings`, `anyio`. Do not add others.
- Unit tests never touch the network. All HTTP is mocked with `respx`.
- Test-driven: write the failing test, watch it fail, then implement.
- Credentials are `SecretStr` and must never appear in logs, exception messages, or committed files.
- Code, comments, identifiers, docstrings, documentation and commit messages in English.
- Conventional Commits. Never `git push` — the user pushes.
- Base URL default: `https://api.cloud.heidi-pass.com`. Default timeout: `30.0` seconds.
- `WalletType` values: `UNSET`, `APPLE`, `GOOGLE`. `PassState` values: `New`, `Install pending`, `Update pending`, `Delete pending`, `Active`, `Inactive`.

## File Structure

| File | Responsibility |
| --- | --- |
| `pyproject.toml` | Package metadata, dependencies, ruff/pytest/ty configuration |
| `Makefile` | `lint`, `reformat`, `test-local`, `test-integration`, `test-drift` |
| `src/edutap/heidi_api/__init__.py` | Public exports |
| `src/edutap/heidi_api/models.py` | Pydantic models and enums |
| `src/edutap/heidi_api/exceptions.py` | `HeidiError` hierarchy and `error_from_response()` |
| `src/edutap/heidi_api/settings.py` | `HeidiSettings` |
| `src/edutap/heidi_api/auth.py` | `TokenManager` |
| `src/edutap/heidi_api/client.py` | `HeidiClient` |
| `tests/conftest.py` | anyio backend fixture, shared fixtures |
| `tests/data/openapi.json` | Checked-in reference copy of the upstream spec |
| `tests/test_*.py` | One test module per source module |
| `.github/workflows/ci.yml` | CI mirroring local checks |
| `docs/` | Sphinx + MyST documentation |

---

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`, `Makefile`, `.gitignore`, `README.md`
- Create: `src/edutap/heidi_api/__init__.py`
- Create: `tests/conftest.py`, `tests/test_package.py`

**Interfaces:**
- Consumes: nothing.
- Produces: an installed, importable package `edutap.heidi_api` exposing `__version__: str`; a pytest setup where async tests run under anyio's asyncio backend; make targets `lint`, `reformat`, `test-local`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_package.py`:

```python
"""Smoke tests for the package itself."""


def test_package_exposes_a_version() -> None:
    import edutap.heidi_api

    assert isinstance(edutap.heidi_api.__version__, str)
    assert edutap.heidi_api.__version__
```

Create `tests/conftest.py`:

```python
"""Shared pytest fixtures."""

import pytest


@pytest.fixture
def anyio_backend() -> str:
    """Run every anyio test on asyncio only, not on trio."""
    return "asyncio"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_package.py -v`
Expected: FAIL — no `pyproject.toml`, no environment, `ModuleNotFoundError: No module named 'edutap'`.

- [ ] **Step 3: Write the scaffolding**

Create `pyproject.toml`:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "edutap.heidi_api"
version = "0.1.0"
description = "Pythonic async client for the HEIDI Cloud Service API"
readme = "README.md"
requires-python = ">=3.12"
license = { text = "EUPL-1.2" }
authors = [{ name = "eduTAP" }]
classifiers = [
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Programming Language :: Python :: 3.14",
    "Framework :: AsyncIO",
]
dependencies = [
    "anyio>=4.4",
    "httpx>=0.27",
    "pydantic>=2.8",
    "pydantic-settings>=2.4",
]

[project.optional-dependencies]
dev = [
    "pdbp",
    "pytest>=8.2",
    "respx>=0.21",
    "ruff>=0.6",
    "ty",
]

[project.urls]
Source = "https://github.com/edutap-eu/edutap.heidi_api"

[tool.hatch.build.targets.wheel]
packages = ["src/edutap"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-markers"
markers = [
    "integration: talks to the live HEIDI API, needs credentials",
    "drift: fetches the live OpenAPI spec over the network",
]

[tool.ruff]
line-length = 88
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "F", "W", "B", "I", "UP", "D", "S"]
ignore = ["D203", "D213"]

[tool.ruff.lint.pydocstyle]
convention = "pep257"

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["D", "S101"]

[tool.ty.src]
root = "./src"
```

`anyio` ships its pytest plugin as part of the base package, so async tests need
no extra test dependency — `pytest.mark.anyio` works once `anyio` is installed.

Create `src/edutap/heidi_api/__init__.py`:

```python
"""Pythonic async client for the HEIDI Cloud Service API."""

from importlib.metadata import version


__version__ = version("edutap.heidi_api")

__all__ = ["__version__"]
```

Create `Makefile`:

```makefile
.PHONY: install lint reformat test-local test-integration test-drift

install:
	uv venv
	uv pip install -U -e ".[dev]"

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests
	uv run ty check

reformat:
	uv run ruff format src tests
	uv run ruff check --fix src tests

test-local:
	uv run pytest -m "not integration and not drift"

test-integration:
	uv run pytest -m integration

test-drift:
	uv run pytest -m drift
```

Create `.gitignore`:

```gitignore
__pycache__/
*.py[cod]
.venv/
.pytest_cache/
.ruff_cache/
dist/
build/
*.egg-info/
.env
docs/_build/
```

Create `README.md`:

```markdown
# edutap.heidi_api

Pythonic async client for the [HEIDI Cloud Service](https://api.cloud.heidi-pass.com/docs) API.

## Installation

```console
uv pip install -U -e ".[dev]"
```

## Usage

```python
from edutap.heidi_api import HeidiClient

async with HeidiClient() as heidi:
    templates = await heidi.list_pass_templates()
```

Configuration is read from the environment: `HEIDI_USERNAME`, `HEIDI_PASSWORD`,
optionally `HEIDI_BASE_URL` and `HEIDI_TIMEOUT`.

## Development

```console
make install
make lint
make test-local
```
```

- [ ] **Step 4: Create the environment and run the tests**

Run:
```bash
make install
uv run pytest tests/test_package.py -v
```
Expected: 1 passed.

- [ ] **Step 5: Verify lint is clean**

Run: `make lint`
Expected: ruff reports no issues; `ty check` reports no errors.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml Makefile .gitignore README.md src tests
git commit -m "chore: scaffold the edutap.heidi_api package"
```

---

### Task 2: Models

**Files:**
- Create: `src/edutap/heidi_api/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `WalletType`, `PassState` (both `StrEnum`), and the models `PassData`, `PassTemplate`, `PayloadPass`, `PayloadInfo`, `PassOperationResponse`, `Token`, `AuthenticatedUser`, `ValidationErrorDetail`, `CreatePassOperation`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_models.py`:

```python
"""Tests for the wire-format models."""

from datetime import datetime
from uuid import UUID

from edutap.heidi_api.models import (
    AuthenticatedUser,
    CreatePassOperation,
    PassData,
    PassOperationResponse,
    PassState,
    PassTemplate,
    PayloadInfo,
    Token,
    ValidationErrorDetail,
    WalletType,
)


def test_wallet_type_values() -> None:
    assert [member.value for member in WalletType] == ["UNSET", "APPLE", "GOOGLE"]


def test_pass_state_keeps_the_api_spelling() -> None:
    assert PassState.INSTALL_PENDING.value == "Install pending"
    assert PassState("Delete pending") is PassState.DELETE_PENDING


def test_pass_data_parses_an_api_response() -> None:
    data = PassData.model_validate(
        {
            "pass_id": "11111111-1111-1111-1111-111111111111",
            "person_id": "person-42",
            "template_id": "22222222-2222-2222-2222-222222222222",
            "wallet_type": "APPLE",
            "pass_state": "Install pending",
            "last_update": "2026-07-20T10:11:12Z",
            "install_link": None,
        }
    )

    assert data.pass_id == UUID("11111111-1111-1111-1111-111111111111")
    assert data.wallet_type is WalletType.APPLE
    assert data.pass_state is PassState.INSTALL_PENDING
    assert isinstance(data.last_update, datetime)
    assert data.install_link is None


def test_pass_template_parses_wallet_types() -> None:
    template = PassTemplate.model_validate(
        {
            "id": "22222222-2222-2222-2222-222222222222",
            "title": "Student Card",
            "wallet_types": ["APPLE", "GOOGLE"],
        }
    )

    assert template.title == "Student Card"
    assert template.wallet_types == [WalletType.APPLE, WalletType.GOOGLE]


def test_payload_info_defaults_to_empty_collections() -> None:
    info = PayloadInfo.model_validate({"template_display_name": "Student Card"})

    assert info.wallet_types == []
    assert info.passes == []


def test_payload_info_parses_nested_passes() -> None:
    info = PayloadInfo.model_validate(
        {
            "template_display_name": "Student Card",
            "wallet_types": ["GOOGLE"],
            "passes": [
                {
                    "wallet_type": "GOOGLE",
                    "pass_state": "Active",
                    "install_link": "https://example.org/i",
                }
            ],
        }
    )

    assert info.passes[0].pass_state is PassState.ACTIVE
    assert info.passes[0].install_link == "https://example.org/i"


def test_pass_operation_response_parses() -> None:
    response = PassOperationResponse.model_validate(
        {"pass_id": "11111111-1111-1111-1111-111111111111", "detail": "accepted"}
    )

    assert response.detail == "accepted"


def test_token_parses() -> None:
    token = Token.model_validate({"access_token": "abc", "token_type": "bearer"})

    assert token.access_token == "abc"


def test_authenticated_user_allows_missing_customer() -> None:
    user = AuthenticatedUser.model_validate(
        {
            "display_name": "Ada Lovelace",
            "username": "ada",
            "roles": ["issuer"],
            "customer_id": None,
            "customer_display_name": None,
        }
    )

    assert user.roles == ["issuer"]
    assert user.customer_id is None


def test_validation_error_detail_parses_mixed_location() -> None:
    detail = ValidationErrorDetail.model_validate(
        {"loc": ["body", 0, "person_id"], "msg": "field required", "type": "missing"}
    )

    assert detail.loc == ["body", 0, "person_id"]


def test_create_pass_operation_serialises_enum_as_string() -> None:
    operation = CreatePassOperation(
        wallet_type=WalletType.APPLE,
        template_id=UUID("22222222-2222-2222-2222-222222222222"),
        person_id="person-42",
    )

    assert operation.model_dump(mode="json") == {
        "wallet_type": "APPLE",
        "template_id": "22222222-2222-2222-2222-222222222222",
        "person_id": "person-42",
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'edutap.heidi_api.models'`.

- [ ] **Step 3: Write the implementation**

Create `src/edutap/heidi_api/models.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_models.py -v`
Expected: 11 passed.

- [ ] **Step 5: Commit**

```bash
git add src/edutap/heidi_api/models.py tests/test_models.py
git commit -m "feat: add wire-format models for the HEIDI API"
```

---

### Task 3: Exceptions

**Files:**
- Create: `src/edutap/heidi_api/exceptions.py`
- Test: `tests/test_exceptions.py`

**Interfaces:**
- Consumes: `ValidationErrorDetail` from `models`.
- Produces:
  - `HeidiError(message, *, status_code=None, request_url=None, body=None)` with attributes `message`, `status_code`, `request_url`, `body`.
  - Subclasses `HeidiAuthError`, `HeidiNotFoundError`, `HeidiConflictError`, `HeidiValidationError` (extra attribute `errors: list[ValidationErrorDetail]`), `HeidiRateLimitError` (extra attribute `retry_after: float | None`), `HeidiServerError`.
  - `error_from_response(response: httpx.Response) -> HeidiError | None` — returns `None` for any status below 400.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_exceptions.py`:

```python
"""Tests for the exception hierarchy and the response mapper."""

import httpx
import pytest

from edutap.heidi_api.exceptions import (
    HeidiAuthError,
    HeidiConflictError,
    HeidiError,
    HeidiNotFoundError,
    HeidiRateLimitError,
    HeidiServerError,
    HeidiValidationError,
    error_from_response,
)


def _response(status_code: int, **kwargs: object) -> httpx.Response:
    request = httpx.Request("GET", "https://api.example.org/api/v1/pass")
    return httpx.Response(status_code, request=request, **kwargs)


def test_success_maps_to_no_error() -> None:
    assert error_from_response(_response(200)) is None
    assert error_from_response(_response(202)) is None


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (401, HeidiAuthError),
        (404, HeidiNotFoundError),
        (409, HeidiConflictError),
        (422, HeidiValidationError),
        (429, HeidiRateLimitError),
        (500, HeidiServerError),
        (503, HeidiServerError),
    ],
)
def test_status_codes_map_to_their_exception(
    status_code: int, expected: type[HeidiError]
) -> None:
    error = error_from_response(_response(status_code))

    assert isinstance(error, expected)
    assert error.status_code == status_code
    assert error.request_url == "https://api.example.org/api/v1/pass"


def test_unmapped_client_error_maps_to_the_base_error() -> None:
    error = error_from_response(_response(418))

    assert type(error) is HeidiError
    assert error.status_code == 418


def test_every_error_is_a_heidi_error() -> None:
    for status_code in (401, 404, 409, 422, 429, 500):
        assert isinstance(error_from_response(_response(status_code)), HeidiError)


def test_validation_error_exposes_parsed_details() -> None:
    error = error_from_response(
        _response(
            422,
            json={
                "detail": [
                    {"loc": ["body", "person_id"], "msg": "field required", "type": "missing"}
                ]
            },
        )
    )

    assert isinstance(error, HeidiValidationError)
    assert error.errors[0].msg == "field required"
    assert error.errors[0].loc == ["body", "person_id"]


def test_validation_error_survives_an_unparsable_body() -> None:
    error = error_from_response(_response(422, text="not json"))

    assert isinstance(error, HeidiValidationError)
    assert error.errors == []


def test_rate_limit_error_reads_retry_after() -> None:
    error = error_from_response(_response(429, headers={"Retry-After": "12"}))

    assert isinstance(error, HeidiRateLimitError)
    assert error.retry_after == 12.0


def test_rate_limit_error_without_header() -> None:
    error = error_from_response(_response(429))

    assert isinstance(error, HeidiRateLimitError)
    assert error.retry_after is None


def test_error_keeps_the_response_body() -> None:
    error = error_from_response(_response(404, text="pass not found"))

    assert error.body == "pass not found"
    assert "404" in str(error)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_exceptions.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'edutap.heidi_api.exceptions'`.

- [ ] **Step 3: Write the implementation**

Create `src/edutap/heidi_api/exceptions.py`:

```python
"""Exceptions raised by the HEIDI client."""

import httpx
from pydantic import ValidationError as PydanticValidationError

from edutap.heidi_api.models import ValidationErrorDetail


class HeidiError(Exception):
    """Base class for every error answer of the HEIDI API."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        request_url: str | None = None,
        body: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.request_url = request_url
        self.body = body


class HeidiAuthError(HeidiError):
    """Authentication failed or the access token is not accepted (401)."""


class HeidiNotFoundError(HeidiError):
    """The requested pass, template or person does not exist (404)."""


class HeidiConflictError(HeidiError):
    """The pass is busy with another operation (409)."""


class HeidiValidationError(HeidiError):
    """The request was rejected as invalid (422)."""

    def __init__(
        self,
        message: str,
        *,
        errors: list[ValidationErrorDetail] | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(message, **kwargs)  # type: ignore[arg-type]
        self.errors = errors or []


class HeidiRateLimitError(HeidiError):
    """Too many requests (429)."""

    def __init__(
        self,
        message: str,
        *,
        retry_after: float | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(message, **kwargs)  # type: ignore[arg-type]
        self.retry_after = retry_after


class HeidiServerError(HeidiError):
    """The HEIDI service failed to handle the request (5xx)."""


_STATUS_MAP: dict[int, type[HeidiError]] = {
    401: HeidiAuthError,
    404: HeidiNotFoundError,
    409: HeidiConflictError,
}


def _validation_details(response: httpx.Response) -> list[ValidationErrorDetail]:
    """Parse the ``detail`` list of a FastAPI validation error response."""
    try:
        payload = response.json()
    except ValueError:
        return []
    if not isinstance(payload, dict):
        return []
    try:
        return [
            ValidationErrorDetail.model_validate(entry)
            for entry in payload.get("detail", [])
        ]
    except (PydanticValidationError, TypeError):
        return []


def _retry_after(response: httpx.Response) -> float | None:
    """Read the ``Retry-After`` header as seconds, if it is a number."""
    raw = response.headers.get("Retry-After")
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def error_from_response(response: httpx.Response) -> HeidiError | None:
    """Map an HTTP response to a :class:`HeidiError`, or ``None`` if it is fine."""
    if response.status_code < 400:
        return None

    message = f"HEIDI API returned {response.status_code} for {response.request.url}"
    common = {
        "status_code": response.status_code,
        "request_url": str(response.request.url),
        "body": response.text,
    }

    if response.status_code == 422:
        return HeidiValidationError(
            message, errors=_validation_details(response), **common
        )
    if response.status_code == 429:
        return HeidiRateLimitError(message, retry_after=_retry_after(response), **common)
    if response.status_code >= 500:
        return HeidiServerError(message, **common)
    return _STATUS_MAP.get(response.status_code, HeidiError)(message, **common)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_exceptions.py -v`
Expected: all passed (17 test cases including the parametrised ones).

- [ ] **Step 5: Commit**

```bash
git add src/edutap/heidi_api/exceptions.py tests/test_exceptions.py
git commit -m "feat: add typed exceptions for HEIDI API error responses"
```

---

### Task 4: Settings

**Files:**
- Create: `src/edutap/heidi_api/settings.py`
- Test: `tests/test_settings.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `HeidiSettings` with fields `base_url: HttpUrl`, `username: str`, `password: SecretStr`, `timeout: float`, env prefix `HEIDI_`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_settings.py`:

```python
"""Tests for configuration handling."""

import pytest
from pydantic import SecretStr, ValidationError

from edutap.heidi_api.settings import HeidiSettings


def test_settings_read_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HEIDI_USERNAME", "ada")
    monkeypatch.setenv("HEIDI_PASSWORD", "s3cret")

    settings = HeidiSettings()

    assert settings.username == "ada"
    assert settings.password == SecretStr("s3cret")
    assert str(settings.base_url) == "https://api.cloud.heidi-pass.com/"
    assert settings.timeout == 30.0


def test_base_url_and_timeout_are_overridable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HEIDI_USERNAME", "ada")
    monkeypatch.setenv("HEIDI_PASSWORD", "s3cret")
    monkeypatch.setenv("HEIDI_BASE_URL", "https://staging.example.org")
    monkeypatch.setenv("HEIDI_TIMEOUT", "5")

    settings = HeidiSettings()

    assert str(settings.base_url) == "https://staging.example.org/"
    assert settings.timeout == 5.0


def test_missing_credentials_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HEIDI_USERNAME", raising=False)
    monkeypatch.delenv("HEIDI_PASSWORD", raising=False)

    with pytest.raises(ValidationError):
        HeidiSettings(_env_file=None)


def test_password_is_not_leaked_by_repr() -> None:
    settings = HeidiSettings(username="ada", password=SecretStr("s3cret"))

    assert "s3cret" not in repr(settings)
    assert settings.password.get_secret_value() == "s3cret"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_settings.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'edutap.heidi_api.settings'`.

- [ ] **Step 3: Write the implementation**

Create `src/edutap/heidi_api/settings.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_settings.py -v`
Expected: 4 passed.

If `test_missing_credentials_are_rejected` fails because a developer `.env` file
supplies the credentials, that is the reason `_env_file=None` is passed in that
test — keep it.

- [ ] **Step 5: Commit**

```bash
git add src/edutap/heidi_api/settings.py tests/test_settings.py
git commit -m "feat: add settings for base URL, credentials and timeout"
```

---

### Task 5: Token manager

**Files:**
- Create: `src/edutap/heidi_api/auth.py`
- Test: `tests/test_auth.py`

**Interfaces:**
- Consumes: `HeidiSettings`, `Token`, `error_from_response`, `HeidiAuthError`.
- Produces: `TokenManager(settings: HeidiSettings, http_client: httpx.AsyncClient)` with
  - `async def token(self) -> str` — returns the cached token, fetching it on first use.
  - `async def refresh(self, stale_token: str) -> str` — fetches a new token unless another task already replaced `stale_token`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_auth.py`:

```python
"""Tests for the OAuth2 token lifecycle."""

import anyio
import httpx
import pytest
import respx
from pydantic import SecretStr

from edutap.heidi_api.auth import TokenManager
from edutap.heidi_api.exceptions import HeidiAuthError
from edutap.heidi_api.settings import HeidiSettings


pytestmark = pytest.mark.anyio

BASE_URL = "https://api.example.org"
TOKEN_URL = f"{BASE_URL}/security/token"


@pytest.fixture
def settings() -> HeidiSettings:
    return HeidiSettings(
        base_url="https://api.example.org",
        username="ada",
        password=SecretStr("s3cret"),
    )


@pytest.fixture
async def http_client() -> httpx.AsyncClient:
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        yield client


async def test_token_is_fetched_on_first_use(
    settings: HeidiSettings, http_client: httpx.AsyncClient
) -> None:
    with respx.mock(assert_all_called=True) as mock:
        route = mock.post(TOKEN_URL).respond(
            json={"access_token": "token-1", "token_type": "bearer"}
        )
        manager = TokenManager(settings, http_client)

        assert await manager.token() == "token-1"

    request = route.calls[0].request
    assert request.headers["content-type"] == "application/x-www-form-urlencoded"
    assert request.content == b"grant_type=password&username=ada&password=s3cret"


async def test_token_is_cached(
    settings: HeidiSettings, http_client: httpx.AsyncClient
) -> None:
    with respx.mock as mock:
        route = mock.post(TOKEN_URL).respond(
            json={"access_token": "token-1", "token_type": "bearer"}
        )
        manager = TokenManager(settings, http_client)

        assert await manager.token() == "token-1"
        assert await manager.token() == "token-1"

    assert route.call_count == 1


async def test_refresh_fetches_a_new_token(
    settings: HeidiSettings, http_client: httpx.AsyncClient
) -> None:
    with respx.mock as mock:
        mock.post(TOKEN_URL).mock(
            side_effect=[
                httpx.Response(200, json={"access_token": "token-1", "token_type": "bearer"}),
                httpx.Response(200, json={"access_token": "token-2", "token_type": "bearer"}),
            ]
        )
        manager = TokenManager(settings, http_client)
        first = await manager.token()

        assert await manager.refresh(first) == "token-2"
        assert await manager.token() == "token-2"


async def test_refresh_is_skipped_when_another_task_already_refreshed(
    settings: HeidiSettings, http_client: httpx.AsyncClient
) -> None:
    with respx.mock as mock:
        route = mock.post(TOKEN_URL).mock(
            side_effect=[
                httpx.Response(200, json={"access_token": "token-1", "token_type": "bearer"}),
                httpx.Response(200, json={"access_token": "token-2", "token_type": "bearer"}),
            ]
        )
        manager = TokenManager(settings, http_client)
        stale = await manager.token()

        async with anyio.create_task_group() as task_group:
            task_group.start_soon(manager.refresh, stale)
            task_group.start_soon(manager.refresh, stale)

        assert await manager.token() == "token-2"

    assert route.call_count == 2  # initial fetch plus exactly one refresh


async def test_rejected_credentials_raise_an_auth_error(
    settings: HeidiSettings, http_client: httpx.AsyncClient
) -> None:
    with respx.mock as mock:
        mock.post(TOKEN_URL).respond(401, text="bad credentials")
        manager = TokenManager(settings, http_client)

        with pytest.raises(HeidiAuthError):
            await manager.token()


async def test_server_error_while_fetching_the_token_is_raised(
    settings: HeidiSettings, http_client: httpx.AsyncClient
) -> None:
    from edutap.heidi_api.exceptions import HeidiServerError

    with respx.mock as mock:
        mock.post(TOKEN_URL).respond(500, text="boom")
        manager = TokenManager(settings, http_client)

        with pytest.raises(HeidiServerError):
            await manager.token()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_auth.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'edutap.heidi_api.auth'`.

- [ ] **Step 3: Write the implementation**

Create `src/edutap/heidi_api/auth.py`:

```python
"""Access token lifecycle for the HEIDI client."""

import anyio
import httpx

from edutap.heidi_api.exceptions import error_from_response
from edutap.heidi_api.models import Token
from edutap.heidi_api.settings import HeidiSettings


TOKEN_PATH = "/security/token"


class TokenManager:
    """Fetches and caches the OAuth2 access token.

    The token carries no expiry, so expiry is detected reactively: the client
    calls :meth:`refresh` after an authenticated request answered ``401``.
    """

    def __init__(self, settings: HeidiSettings, http_client: httpx.AsyncClient) -> None:
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
        """Perform the OAuth2 password grant."""
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_auth.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/edutap/heidi_api/auth.py tests/test_auth.py
git commit -m "feat: add token manager with lazy fetch and single refresh"
```

---

### Task 6: Client core

**Files:**
- Create: `src/edutap/heidi_api/client.py`
- Test: `tests/test_client_core.py`
- Modify: `tests/conftest.py` (add shared client fixtures)

**Interfaces:**
- Consumes: `HeidiSettings`, `TokenManager`, `error_from_response`, `AuthenticatedUser`.
- Produces:
  - `HeidiClient(settings: HeidiSettings | None = None, http_client: httpx.AsyncClient | None = None)`
  - `async def __aenter__(self) -> HeidiClient` / `async def __aexit__(...) -> None`
  - `async def aclose(self) -> None` — closes the HTTP client only when the client created it.
  - `async def _request(self, method: str, url: str, *, params: dict | None = None, json: object | None = None) -> httpx.Response` — private, used by every endpoint method in Tasks 7 and 8.
  - `async def whoami(self) -> AuthenticatedUser`
- Fixtures produced for later tasks: `settings`, `http_client`, `heidi` (a `HeidiClient` bound to `https://api.example.org` with the token endpoint already mocked), and the constant `BASE_URL`.

- [ ] **Step 1: Write the failing tests**

Replace `tests/conftest.py` with:

```python
"""Shared pytest fixtures."""

from collections.abc import AsyncIterator

import httpx
import pytest
import respx
from pydantic import SecretStr

from edutap.heidi_api.client import HeidiClient
from edutap.heidi_api.settings import HeidiSettings


BASE_URL = "https://api.example.org"


@pytest.fixture
def anyio_backend() -> str:
    """Run every anyio test on asyncio only, not on trio."""
    return "asyncio"


@pytest.fixture
def settings() -> HeidiSettings:
    return HeidiSettings(
        base_url=BASE_URL,
        username="ada",
        password=SecretStr("s3cret"),
    )


@pytest.fixture
def mock_api() -> AsyncIterator[respx.MockRouter]:
    """Mock every HTTP call and pre-answer the token endpoint."""
    with respx.mock(base_url=BASE_URL, assert_all_called=False) as router:
        router.post("/security/token").respond(
            json={"access_token": "token-1", "token_type": "bearer"}
        )
        yield router


@pytest.fixture
async def heidi(
    settings: HeidiSettings, mock_api: respx.MockRouter
) -> AsyncIterator[HeidiClient]:
    async with HeidiClient(settings=settings) as client:
        yield client


@pytest.fixture
def external_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=BASE_URL)
```

Create `tests/test_client_core.py`:

```python
"""Tests for transport, authentication wiring and error mapping."""

import httpx
import pytest
import respx

from edutap.heidi_api.client import HeidiClient
from edutap.heidi_api.exceptions import (
    HeidiAuthError,
    HeidiConflictError,
    HeidiNotFoundError,
    HeidiServerError,
    HeidiValidationError,
)
from edutap.heidi_api.models import AuthenticatedUser
from edutap.heidi_api.settings import HeidiSettings


pytestmark = pytest.mark.anyio

BASE_URL = "https://api.example.org"  # must match the value in conftest.py

USER_PAYLOAD = {
    "display_name": "Ada Lovelace",
    "username": "ada",
    "roles": ["issuer"],
    "customer_id": None,
    "customer_display_name": None,
}


async def test_whoami_returns_the_authenticated_user(
    heidi: HeidiClient, mock_api: respx.MockRouter
) -> None:
    mock_api.get("/security/authenticated").respond(json=USER_PAYLOAD)

    user = await heidi.whoami()

    assert isinstance(user, AuthenticatedUser)
    assert user.username == "ada"


async def test_requests_carry_the_bearer_token(
    heidi: HeidiClient, mock_api: respx.MockRouter
) -> None:
    route = mock_api.get("/security/authenticated").respond(json=USER_PAYLOAD)

    await heidi.whoami()

    assert route.calls[0].request.headers["authorization"] == "Bearer token-1"


async def test_a_401_triggers_exactly_one_reauthentication(
    heidi: HeidiClient, mock_api: respx.MockRouter
) -> None:
    token_route = mock_api.post("/security/token").mock(
        side_effect=[
            httpx.Response(200, json={"access_token": "token-1", "token_type": "bearer"}),
            httpx.Response(200, json={"access_token": "token-2", "token_type": "bearer"}),
        ]
    )
    route = mock_api.get("/security/authenticated").mock(
        side_effect=[
            httpx.Response(401, text="expired"),
            httpx.Response(200, json=USER_PAYLOAD),
        ]
    )

    user = await heidi.whoami()

    assert user.username == "ada"
    assert token_route.call_count == 2
    assert route.calls[1].request.headers["authorization"] == "Bearer token-2"


async def test_a_second_401_raises_an_auth_error(
    heidi: HeidiClient, mock_api: respx.MockRouter
) -> None:
    mock_api.get("/security/authenticated").respond(401, text="nope")

    with pytest.raises(HeidiAuthError):
        await heidi.whoami()


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (404, HeidiNotFoundError),
        (409, HeidiConflictError),
        (422, HeidiValidationError),
        (500, HeidiServerError),
    ],
)
async def test_error_statuses_raise_typed_exceptions(
    heidi: HeidiClient,
    mock_api: respx.MockRouter,
    status_code: int,
    expected: type[Exception],
) -> None:
    mock_api.get("/security/authenticated").respond(status_code, text="failed")

    with pytest.raises(expected):
        await heidi.whoami()


async def test_client_closes_its_own_http_client(
    settings: HeidiSettings, mock_api: respx.MockRouter
) -> None:
    client = HeidiClient(settings=settings)

    async with client:
        pass

    assert client._http_client.is_closed


async def test_an_injected_http_client_is_not_closed(
    settings: HeidiSettings,
    mock_api: respx.MockRouter,
    external_http_client: httpx.AsyncClient,
) -> None:
    async with HeidiClient(settings=settings, http_client=external_http_client):
        pass

    assert not external_http_client.is_closed
    await external_http_client.aclose()


async def test_settings_are_read_from_the_environment_by_default(
    monkeypatch: pytest.MonkeyPatch, mock_api: respx.MockRouter
) -> None:
    monkeypatch.setenv("HEIDI_BASE_URL", BASE_URL)
    monkeypatch.setenv("HEIDI_USERNAME", "ada")
    monkeypatch.setenv("HEIDI_PASSWORD", "s3cret")
    mock_api.get("/security/authenticated").respond(json=USER_PAYLOAD)

    async with HeidiClient() as client:
        user = await client.whoami()

    assert user.display_name == "Ada Lovelace"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_client_core.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'edutap.heidi_api.client'`.

- [ ] **Step 3: Write the implementation**

Create `src/edutap/heidi_api/client.py`:

```python
"""Async client for the HEIDI Cloud Service API."""

from types import TracebackType
from typing import Any, Self

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
        self._settings = settings or HeidiSettings()
        self._owns_http_client = http_client is None
        self._http_client = http_client or httpx.AsyncClient(
            base_url=str(self._settings.base_url),
            timeout=self._settings.timeout,
        )
        self._tokens = TokenManager(self._settings, self._http_client)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
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
        params: dict[str, Any] | None = None,
        json: Any = None,
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
        params: dict[str, Any] | None,
        json: Any,
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_client_core.py tests/test_auth.py -v`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add src/edutap/heidi_api/client.py tests/test_client_core.py tests/conftest.py
git commit -m "feat: add HeidiClient core with auth, retry-once and error mapping"
```

---

### Task 7: Issuer endpoints

**Files:**
- Modify: `src/edutap/heidi_api/client.py` (append methods to `HeidiClient`)
- Test: `tests/test_client_issuer.py`

**Interfaces:**
- Consumes: `HeidiClient._request`, models from Task 2.
- Produces, all on `HeidiClient`:
  - `async def get_pass(self, pass_id: UUID | str) -> PassData`
  - `async def update_pass(self, pass_id: UUID | str) -> PassOperationResponse`
  - `async def delete_pass(self, pass_id: UUID | str) -> PassOperationResponse`
  - `async def create_pass(self, *, template_id: UUID | str, person_id: str, wallet_type: WalletType | str) -> PassOperationResponse`
  - `async def get_passes(self, template_id: UUID | str, person_id: str) -> list[PassData]`
  - `async def update_passes(self, template_id: UUID | str, person_id: str) -> PassOperationResponse`
  - `async def delete_passes(self, template_id: UUID | str, person_id: str) -> PassOperationResponse`
  - `async def list_wallet_types(self) -> list[WalletType]`
  - `async def list_pass_templates(self) -> list[PassTemplate]`
  - `async def search_persons(self, template_id: UUID | str, term: str) -> list[dict[str, Any]]`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_client_issuer.py`:

```python
"""Tests for the issuer endpoints."""

import pytest
import respx

from edutap.heidi_api.client import HeidiClient
from edutap.heidi_api.models import (
    PassData,
    PassOperationResponse,
    PassState,
    PassTemplate,
    WalletType,
)


pytestmark = pytest.mark.anyio

PASS_ID = "11111111-1111-1111-1111-111111111111"
TEMPLATE_ID = "22222222-2222-2222-2222-222222222222"
PERSON_ID = "person-42"

PASS_PAYLOAD = {
    "pass_id": PASS_ID,
    "person_id": PERSON_ID,
    "template_id": TEMPLATE_ID,
    "wallet_type": "APPLE",
    "pass_state": "Active",
    "last_update": "2026-07-20T10:11:12Z",
    "install_link": "https://example.org/install",
}
OPERATION_PAYLOAD = {"pass_id": PASS_ID, "detail": "accepted"}


async def test_get_pass(heidi: HeidiClient, mock_api: respx.MockRouter) -> None:
    mock_api.get(f"/api/v1/pass/{PASS_ID}").respond(json=PASS_PAYLOAD)

    result = await heidi.get_pass(PASS_ID)

    assert isinstance(result, PassData)
    assert result.pass_state is PassState.ACTIVE
    assert result.install_link == "https://example.org/install"


async def test_update_pass(heidi: HeidiClient, mock_api: respx.MockRouter) -> None:
    mock_api.put(f"/api/v1/pass/{PASS_ID}").respond(202, json=OPERATION_PAYLOAD)

    result = await heidi.update_pass(PASS_ID)

    assert isinstance(result, PassOperationResponse)
    assert result.detail == "accepted"


async def test_delete_pass(heidi: HeidiClient, mock_api: respx.MockRouter) -> None:
    mock_api.delete(f"/api/v1/pass/{PASS_ID}").respond(202, json=OPERATION_PAYLOAD)

    result = await heidi.delete_pass(PASS_ID)

    assert result.detail == "accepted"


async def test_create_pass_sends_the_operation_body(
    heidi: HeidiClient, mock_api: respx.MockRouter
) -> None:
    route = mock_api.post("/api/v1/pass").respond(202, json=OPERATION_PAYLOAD)

    result = await heidi.create_pass(
        template_id=TEMPLATE_ID,
        person_id=PERSON_ID,
        wallet_type=WalletType.APPLE,
    )

    assert result.detail == "accepted"
    import json

    assert json.loads(route.calls[0].request.content) == {
        "wallet_type": "APPLE",
        "template_id": TEMPLATE_ID,
        "person_id": PERSON_ID,
    }


async def test_create_pass_accepts_a_plain_string_wallet_type(
    heidi: HeidiClient, mock_api: respx.MockRouter
) -> None:
    route = mock_api.post("/api/v1/pass").respond(202, json=OPERATION_PAYLOAD)

    await heidi.create_pass(
        template_id=TEMPLATE_ID, person_id=PERSON_ID, wallet_type="GOOGLE"
    )

    import json

    assert json.loads(route.calls[0].request.content)["wallet_type"] == "GOOGLE"


async def test_get_passes_returns_a_list(
    heidi: HeidiClient, mock_api: respx.MockRouter
) -> None:
    mock_api.get(f"/api/v1/passes/{TEMPLATE_ID}/{PERSON_ID}").respond(
        json=[PASS_PAYLOAD]
    )

    result = await heidi.get_passes(TEMPLATE_ID, PERSON_ID)

    assert [item.pass_id for item in result] == [PASS_PAYLOAD["pass_id"]]
    assert isinstance(result[0], PassData)


async def test_update_passes(heidi: HeidiClient, mock_api: respx.MockRouter) -> None:
    mock_api.put(f"/api/v1/passes/{TEMPLATE_ID}/{PERSON_ID}").respond(
        202, json=OPERATION_PAYLOAD
    )

    result = await heidi.update_passes(TEMPLATE_ID, PERSON_ID)

    assert result.detail == "accepted"


async def test_delete_passes(heidi: HeidiClient, mock_api: respx.MockRouter) -> None:
    mock_api.delete(f"/api/v1/passes/{TEMPLATE_ID}/{PERSON_ID}").respond(
        202, json=OPERATION_PAYLOAD
    )

    result = await heidi.delete_passes(TEMPLATE_ID, PERSON_ID)

    assert result.detail == "accepted"


async def test_list_wallet_types(heidi: HeidiClient, mock_api: respx.MockRouter) -> None:
    mock_api.get("/api/v1/wallet_types").respond(json=["APPLE", "GOOGLE"])

    result = await heidi.list_wallet_types()

    assert result == [WalletType.APPLE, WalletType.GOOGLE]


async def test_list_pass_templates(
    heidi: HeidiClient, mock_api: respx.MockRouter
) -> None:
    mock_api.get("/api/v1/pass_templates").respond(
        json=[{"id": TEMPLATE_ID, "title": "Student Card", "wallet_types": ["APPLE"]}]
    )

    result = await heidi.list_pass_templates()

    assert isinstance(result[0], PassTemplate)
    assert result[0].title == "Student Card"


async def test_search_persons_returns_raw_dicts(
    heidi: HeidiClient, mock_api: respx.MockRouter
) -> None:
    mock_api.get(f"/api/v1/search_persons/{TEMPLATE_ID}/ada").respond(
        json=[{"person_id": PERSON_ID, "display_name": "Ada Lovelace"}]
    )

    result = await heidi.search_persons(TEMPLATE_ID, "ada")

    assert result == [{"person_id": PERSON_ID, "display_name": "Ada Lovelace"}]


async def test_person_search_term_is_url_encoded(
    heidi: HeidiClient, mock_api: respx.MockRouter
) -> None:
    route = mock_api.get(f"/api/v1/search_persons/{TEMPLATE_ID}/ada%20lovelace").respond(
        json=[]
    )

    await heidi.search_persons(TEMPLATE_ID, "ada lovelace")

    assert route.called
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_client_issuer.py -v`
Expected: FAIL with `AttributeError: 'HeidiClient' object has no attribute 'get_pass'`.

- [ ] **Step 3: Write the implementation**

Add these imports at the top of `src/edutap/heidi_api/client.py`:

```python
from urllib.parse import quote
from uuid import UUID

from pydantic import TypeAdapter

from edutap.heidi_api.models import (
    AuthenticatedUser,
    CreatePassOperation,
    PassData,
    PassOperationResponse,
    PassTemplate,
    WalletType,
)
```

Add module-level adapters below the imports:

```python
_PASS_LIST = TypeAdapter(list[PassData])
_TEMPLATE_LIST = TypeAdapter(list[PassTemplate])
_WALLET_TYPE_LIST = TypeAdapter(list[WalletType])
```

Append these methods to `HeidiClient` (after `whoami`):

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_client_issuer.py -v`
Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
git add src/edutap/heidi_api/client.py tests/test_client_issuer.py
git commit -m "feat: add issuer endpoints to HeidiClient"
```

---

### Task 8: Self-service endpoints

**Files:**
- Modify: `src/edutap/heidi_api/client.py` (append methods to `HeidiClient`)
- Test: `tests/test_client_self_service.py`

**Interfaces:**
- Consumes: `HeidiClient._request`, `PayloadInfo`, `PassOperationResponse`, `WalletType`.
- Produces, all on `HeidiClient`:
  - `async def get_self_service_payload(self, template_id: UUID | str, person_id: str) -> str`
  - `async def get_self_service_info(self, payload: str) -> PayloadInfo`
  - `async def create_pass_from_payload(self, wallet_type: WalletType | str, payload: str) -> PassOperationResponse`

Remember the API quirk: `payload` is a **query** parameter on both POST endpoints, not a request body.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_client_self_service.py`:

```python
"""Tests for the self-service endpoints."""

import pytest
import respx

from edutap.heidi_api.client import HeidiClient
from edutap.heidi_api.models import PassState, PayloadInfo, WalletType


pytestmark = pytest.mark.anyio

TEMPLATE_ID = "22222222-2222-2222-2222-222222222222"
PERSON_ID = "person-42"
PAYLOAD = "opaque-payload-token"


async def test_get_self_service_payload_returns_the_raw_payload(
    heidi: HeidiClient, mock_api: respx.MockRouter
) -> None:
    mock_api.get(f"/api/v1/self-service/payload/{TEMPLATE_ID}/{PERSON_ID}").respond(
        text=PAYLOAD
    )

    result = await heidi.get_self_service_payload(TEMPLATE_ID, PERSON_ID)

    assert result == PAYLOAD


async def test_get_self_service_info_sends_the_payload_as_a_query_parameter(
    heidi: HeidiClient, mock_api: respx.MockRouter
) -> None:
    route = mock_api.post("/api/v1/self-service/info").respond(
        json={
            "template_display_name": "Student Card",
            "wallet_types": ["APPLE"],
            "passes": [
                {"wallet_type": "APPLE", "pass_state": "Active", "install_link": None}
            ],
        }
    )

    result = await heidi.get_self_service_info(PAYLOAD)

    assert isinstance(result, PayloadInfo)
    assert result.template_display_name == "Student Card"
    assert result.passes[0].pass_state is PassState.ACTIVE
    assert route.calls[0].request.url.params["payload"] == PAYLOAD
    assert route.calls[0].request.content == b""


async def test_create_pass_from_payload(
    heidi: HeidiClient, mock_api: respx.MockRouter
) -> None:
    route = mock_api.post("/api/v1/self-service/create/APPLE").respond(
        202,
        json={"pass_id": "11111111-1111-1111-1111-111111111111", "detail": "accepted"},
    )

    result = await heidi.create_pass_from_payload(WalletType.APPLE, PAYLOAD)

    assert result.detail == "accepted"
    assert route.calls[0].request.url.params["payload"] == PAYLOAD


async def test_create_pass_from_payload_accepts_a_string_wallet_type(
    heidi: HeidiClient, mock_api: respx.MockRouter
) -> None:
    route = mock_api.post("/api/v1/self-service/create/GOOGLE").respond(
        202,
        json={"pass_id": "11111111-1111-1111-1111-111111111111", "detail": "accepted"},
    )

    await heidi.create_pass_from_payload("GOOGLE", PAYLOAD)

    assert route.called
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_client_self_service.py -v`
Expected: FAIL with `AttributeError: 'HeidiClient' object has no attribute 'get_self_service_payload'`.

- [ ] **Step 3: Write the implementation**

Add `PayloadInfo` to the model import in `src/edutap/heidi_api/client.py`, then append to `HeidiClient`:

```python
    async def get_self_service_payload(
        self, template_id: UUID | str, person_id: str
    ) -> str:
        """Return the opaque self-service payload for a person and template.

        The payload has no documented structure; pass it back unchanged to
        :meth:`get_self_service_info` or :meth:`create_pass_from_payload`.
        """
        response = await self._request(
            "GET", f"/api/v1/self-service/payload/{template_id}/{quote(person_id)}"
        )
        return response.text

    async def get_self_service_info(self, payload: str) -> PayloadInfo:
        """Describe what a self-service payload refers to."""
        response = await self._request(
            "POST", "/api/v1/self-service/info", params={"payload": payload}
        )
        return PayloadInfo.model_validate(response.json())

    async def create_pass_from_payload(
        self, wallet_type: WalletType | str, payload: str
    ) -> PassOperationResponse:
        """Create a pass for the person a self-service payload refers to."""
        response = await self._request(
            "POST",
            f"/api/v1/self-service/create/{WalletType(wallet_type).value}",
            params={"payload": payload},
        )
        return PassOperationResponse.model_validate(response.json())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_client_self_service.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/edutap/heidi_api/client.py tests/test_client_self_service.py
git commit -m "feat: add self-service endpoints to HeidiClient"
```

---

### Task 9: Public exports

**Files:**
- Modify: `src/edutap/heidi_api/__init__.py`
- Test: `tests/test_public_api.py`

**Interfaces:**
- Consumes: everything built so far.
- Produces: a stable public import surface — `HeidiClient`, `HeidiSettings`, all models and enums, all exceptions, `__version__`, and a matching `__all__`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_public_api.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_public_api.py -v`
Expected: FAIL — `__all__` currently only contains `__version__`.

- [ ] **Step 3: Write the implementation**

Replace `src/edutap/heidi_api/__init__.py`:

```python
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
```

- [ ] **Step 4: Run the whole unit suite**

Run: `make test-local`
Expected: every test passes.

- [ ] **Step 5: Commit**

```bash
git add src/edutap/heidi_api/__init__.py tests/test_public_api.py
git commit -m "feat: export the public API from the package root"
```

---

### Task 10: OpenAPI drift test

**Files:**
- Create: `tests/data/openapi.json` (downloaded reference copy)
- Create: `tests/test_spec_drift.py`

**Interfaces:**
- Consumes: nothing from the library — this test guards the hand-written models against upstream changes.
- Produces: `make test-drift`, which fails when HEIDI changes its operations or schemas.

- [ ] **Step 1: Download the reference spec**

Run:
```bash
mkdir -p tests/data
curl -sS https://api.cloud.heidi-pass.com/openapi.json -o tests/data/openapi.json
python -c "import json; json.load(open('tests/data/openapi.json'))"
```
Expected: no output — the file is valid JSON.

- [ ] **Step 2: Write the test**

Create `tests/test_spec_drift.py`:

```python
"""Guard the hand-written models against upstream API changes.

This test talks to the live HEIDI service and is therefore excluded from
``make test-local``. Run it with ``make test-drift``.
"""

import json
from pathlib import Path

import httpx
import pytest


pytestmark = [pytest.mark.anyio, pytest.mark.drift]

SPEC_URL = "https://api.cloud.heidi-pass.com/openapi.json"
REFERENCE = Path(__file__).parent / "data" / "openapi.json"
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def _operations(spec: dict) -> set[tuple[str, str]]:
    """Return the set of (method, path) pairs a spec declares."""
    return {
        (method.upper(), path)
        for path, operations in spec["paths"].items()
        for method in operations
        if method in HTTP_METHODS
    }


@pytest.fixture
def reference_spec() -> dict:
    return json.loads(REFERENCE.read_text())


@pytest.fixture
async def live_spec() -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(SPEC_URL)
    response.raise_for_status()
    return response.json()


async def test_no_operations_were_added_or_removed(
    live_spec: dict, reference_spec: dict
) -> None:
    live = _operations(live_spec)
    reference = _operations(reference_spec)

    assert live - reference == set(), "HEIDI added operations"
    assert reference - live == set(), "HEIDI removed operations"


async def test_schemas_are_unchanged(live_spec: dict, reference_spec: dict) -> None:
    live = live_spec["components"]["schemas"]
    reference = reference_spec["components"]["schemas"]

    assert set(live) == set(reference), "the set of schemas changed"
    changed = [name for name in reference if live[name] != reference[name]]
    assert changed == [], f"schemas changed upstream: {changed}"
```

- [ ] **Step 3: Run the drift test**

Run: `make test-drift`
Expected: 2 passed — the reference copy was just downloaded, so it matches.

- [ ] **Step 4: Verify it is excluded from the local suite**

Run: `make test-local`
Expected: the drift tests are deselected; no network call happens.

- [ ] **Step 5: Commit**

```bash
git add tests/data/openapi.json tests/test_spec_drift.py
git commit -m "test: detect drift between the models and the live OpenAPI spec"
```

---

### Task 11: Integration tests

**Files:**
- Create: `tests/test_integration.py`

**Interfaces:**
- Consumes: `HeidiClient` and its read-only methods.
- Produces: `make test-integration`, skipped unless `HEIDI_USERNAME` and `HEIDI_PASSWORD` are set.

Read-only operations only. Never create, update or delete passes here — these tests may run against production.

- [ ] **Step 1: Write the tests**

Create `tests/test_integration.py`:

```python
"""Read-only smoke tests against the live HEIDI service.

Skipped unless ``HEIDI_USERNAME`` and ``HEIDI_PASSWORD`` are set. These tests
never mutate data: they may run against a production installation.
"""

import os

import pytest

from edutap.heidi_api import AuthenticatedUser, HeidiClient, PassTemplate, WalletType


pytestmark = [
    pytest.mark.anyio,
    pytest.mark.integration,
    pytest.mark.skipif(
        not (os.environ.get("HEIDI_USERNAME") and os.environ.get("HEIDI_PASSWORD")),
        reason="HEIDI_USERNAME and HEIDI_PASSWORD are not set",
    ),
]


async def test_whoami_returns_the_configured_user() -> None:
    async with HeidiClient() as heidi:
        user = await heidi.whoami()

    assert isinstance(user, AuthenticatedUser)
    assert user.username == os.environ["HEIDI_USERNAME"]


async def test_wallet_types_are_known_members() -> None:
    async with HeidiClient() as heidi:
        wallet_types = await heidi.list_wallet_types()

    assert all(isinstance(item, WalletType) for item in wallet_types)


async def test_pass_templates_parse() -> None:
    async with HeidiClient() as heidi:
        templates = await heidi.list_pass_templates()

    assert all(isinstance(item, PassTemplate) for item in templates)


async def test_one_client_serves_several_calls() -> None:
    async with HeidiClient() as heidi:
        await heidi.whoami()
        await heidi.list_pass_templates()
        user = await heidi.whoami()

    assert user.username == os.environ["HEIDI_USERNAME"]
```

- [ ] **Step 2: Verify they are skipped without credentials**

Run: `env -u HEIDI_USERNAME -u HEIDI_PASSWORD uv run pytest -m integration -v`
Expected: 4 skipped.

- [ ] **Step 3: Verify they are excluded from the local suite**

Run: `make test-local`
Expected: integration tests are deselected.

- [ ] **Step 4: Run them against the live API if credentials are available**

Run: `make test-integration`
Expected: 4 passed with credentials, 4 skipped without. Report which of the two happened — do not claim the live API was verified if the tests were skipped.

- [ ] **Step 5: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add read-only integration tests against the live API"
```

---

### Task 12: Hooks, tox matrix and CI

**Files:**
- Create: `.pre-commit-config.yaml`, `tox.ini`, `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: the make targets from Task 1.
- Produces: `prek run --all-files` and a GitHub Actions workflow that mirrors the local checks over Python 3.12, 3.13 and 3.14.

- [ ] **Step 1: Write the hook configuration**

Create `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.9
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: check-toml
      - id: check-yaml
      - id: end-of-file-fixer
      - id: trailing-whitespace
```

- [ ] **Step 2: Write the tox configuration**

Create `tox.ini`:

```ini
[tox]
env_list = py312, py313, py314, lint
isolated_build = true

[testenv]
runner = uv-venv-lock-runner
extras = dev
commands = pytest -m "not integration and not drift" {posargs}

[testenv:lint]
skip_install = true
deps =
    ruff
commands =
    ruff check src tests
    ruff format --check src tests
```

- [ ] **Step 3: Write the CI workflow**

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.12", "3.13", "3.14"]
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - name: Install
        run: uv pip install --system -e ".[dev]"
      - name: Test
        run: pytest -m "not integration and not drift"

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - name: Install
        run: uv pip install --system -e ".[dev]"
      - name: Ruff check
        run: ruff check src tests
      - name: Ruff format
        run: ruff format --check src tests
      - name: Type check
        run: ty check
```

- [ ] **Step 4: Verify the hooks and the matrix locally**

Run:
```bash
uvx prek install
uvx prek run --all-files
uvx tox -e py312
```
Expected: hooks pass; the py312 environment runs the unit suite green. If a Python version is missing locally, note it rather than claiming it passed.

- [ ] **Step 5: Commit**

```bash
git add .pre-commit-config.yaml tox.ini .github/workflows/ci.yml
git commit -m "ci: add prek hooks, tox matrix and GitHub Actions workflow"
```

---

### Task 13: Documentation

**Files:**
- Create: `docs/conf.py`, `docs/index.md`, `docs/tutorial.md`, `docs/how-to.md`, `docs/reference.md`, `docs/explanation.md`
- Modify: `pyproject.toml` (add a `docs` extra)

**Interfaces:**
- Consumes: the public API from Task 9.
- Produces: a Sphinx + MyST documentation set following Diataxis, buildable with `make docs`.

Follow the `plone-doc-style` skill when writing the prose.

- [ ] **Step 1: Add the docs extra and make target**

In `pyproject.toml`, add to `[project.optional-dependencies]`:

```toml
docs = [
    "myst-parser",
    "sphinx>=8",
    "sphinx-autodoc2",
]
```

In `Makefile`, add:

```makefile
.PHONY: docs

docs:
	uv run sphinx-build -b html docs docs/_build/html
```

Also add `docs` to the `.PHONY` list at the top.

- [ ] **Step 2: Write the Sphinx configuration**

Create `docs/conf.py`:

```python
"""Sphinx configuration."""

project = "edutap.heidi_api"
author = "eduTAP"

extensions = ["myst_parser", "sphinx.ext.autodoc", "sphinx.ext.napoleon"]

myst_enable_extensions = ["colon_fence", "deflist"]

html_theme = "alabaster"
exclude_patterns = ["_build"]
```

- [ ] **Step 3: Write the pages**

Create `docs/index.md`:

````markdown
# edutap.heidi_api

An async Python client for the HEIDI Cloud Service API.

```{toctree}
:maxdepth: 2

tutorial
how-to
reference
explanation
```
````

Create `docs/tutorial.md`:

````markdown
# Issue your first pass

This tutorial creates a wallet pass for one person and waits until HEIDI
reports it as installed.

## Prerequisites

Install the package and set your credentials:

```console
uv pip install -U edutap.heidi_api
export HEIDI_USERNAME=your-user
export HEIDI_PASSWORD=your-password
```

## Find a template

```python
import anyio

from edutap.heidi_api import HeidiClient


async def main() -> None:
    async with HeidiClient() as heidi:
        for template in await heidi.list_pass_templates():
            print(template.id, template.title, template.wallet_types)


anyio.run(main)
```

## Create a pass and wait for it

Mutating operations answer `202 Accepted`: HEIDI acknowledges the request and
performs it in the background. Poll `get_pass` until the state settles.

```python
import anyio

from edutap.heidi_api import HeidiClient, PassState, WalletType


async def main() -> None:
    async with HeidiClient() as heidi:
        operation = await heidi.create_pass(
            template_id="22222222-2222-2222-2222-222222222222",
            person_id="person-42",
            wallet_type=WalletType.APPLE,
        )
        print("accepted:", operation.detail)

        while True:
            data = await heidi.get_pass(operation.pass_id)
            if data.pass_state is not PassState.INSTALL_PENDING:
                break
            await anyio.sleep(2)

        print(data.pass_state, data.install_link)


anyio.run(main)
```

Hand `data.install_link` to the person — it opens the pass in their wallet.
````

Create `docs/how-to.md`:

````markdown
# How-to guides

## Configure credentials

Settings are read from the environment with the prefix `HEIDI_`:

| Variable | Default |
| --- | --- |
| `HEIDI_USERNAME` | required |
| `HEIDI_PASSWORD` | required |
| `HEIDI_BASE_URL` | `https://api.cloud.heidi-pass.com` |
| `HEIDI_TIMEOUT` | `30.0` |

A `.env` file in the working directory is read as well. To configure the client
explicitly instead:

```python
from pydantic import SecretStr

from edutap.heidi_api import HeidiClient, HeidiSettings

settings = HeidiSettings(username="ada", password=SecretStr("s3cret"))
async with HeidiClient(settings=settings) as heidi:
    ...
```

## Share one HTTP client

Pass your own `httpx.AsyncClient` when the surrounding application already
manages a connection pool. The client you inject is never closed by
`HeidiClient`:

```python
import httpx

from edutap.heidi_api import HeidiClient

async with httpx.AsyncClient(base_url="https://api.cloud.heidi-pass.com") as http:
    async with HeidiClient(http_client=http) as heidi:
        await heidi.whoami()
```

## Handle a pass that is still busy

HEIDI answers `409` when another operation on the same pass is still running:

```python
from edutap.heidi_api import HeidiClient, HeidiConflictError

async with HeidiClient() as heidi:
    try:
        await heidi.update_pass(pass_id)
    except HeidiConflictError:
        ...  # retry later; a previous operation is still pending
```

## Use the self-service flow

```python
async with HeidiClient() as heidi:
    payload = await heidi.get_self_service_payload(template_id, person_id)
    info = await heidi.get_self_service_info(payload)
    if WalletType.GOOGLE in info.wallet_types:
        await heidi.create_pass_from_payload(WalletType.GOOGLE, payload)
```

The payload is opaque — store and forward it unchanged.
````

Create `docs/reference.md` — a table of every `HeidiClient` method with its
signature and the HTTP operation it calls, plus an autodoc section for the
models and exceptions:

````markdown
```{eval-rst}
.. automodule:: edutap.heidi_api.models
   :members:

.. automodule:: edutap.heidi_api.exceptions
   :members:
```
````

Create `docs/explanation.md` — explain why mutating operations answer `202` and
what that means for callers (the pass state moves through `Install pending`,
`Update pending` or `Delete pending`; results are eventually consistent), and
why the client re-authenticates reactively rather than tracking expiry.

- [ ] **Step 4: Build the documentation**

Run:
```bash
uv pip install -U -e ".[dev,docs]"
make docs
```
Expected: Sphinx finishes with `build succeeded` and no warnings about missing
documents or broken references.

- [ ] **Step 5: Commit**

```bash
git add docs pyproject.toml Makefile
git commit -m "docs: add Sphinx documentation following Diataxis"
```

---

### Task 14: Final verification

**Files:** none — this task only verifies.

- [ ] **Step 1: Run the full local gate**

Run:
```bash
make lint
make test-local
```
Expected: ruff clean, `ty check` clean, all unit tests pass. Paste the actual
summary lines into the report; do not summarise from memory.

- [ ] **Step 2: Run the drift test**

Run: `make test-drift`
Expected: passes, confirming the models still match the live API.

- [ ] **Step 3: Check the working tree is clean**

Run: `git status --short`
Expected: no output.

- [ ] **Step 4: Report**

Report changed files, the test commands run with their real output, remaining
risks, and open points. Do not push — the user pushes.
