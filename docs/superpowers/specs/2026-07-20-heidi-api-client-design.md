# Design: `edutap.heidi_api` — Pythonic client for the HEIDI Cloud API

Date: 2026-07-20
Status: approved

## Goal

Provide an async Python client library (SDK) for the HEIDI Cloud Service
(<https://api.cloud.heidi-pass.com>), so that eduTAP code can issue, update and
delete wallet passes without hand-rolling HTTP calls.

Non-goals: no CLI, no wrapper service, no Docker environment (this is a library,
not a web service).

## Upstream API

The service is a FastAPI application exposing OpenAPI 3.1 at
`/openapi.json`. It has 15 operations in three groups:

| Group | Operations |
| --- | --- |
| `heidi.cloud.security` | `POST /security/token`, `GET /security/authenticated` |
| `heidi.cloud.api.issuer` | pass CRUD, pass listing per template/person, wallet types, pass templates, person search |
| `heidi.cloud.api.self-service` | payload retrieval, payload info, pass creation from payload |

Authentication is OAuth2 password flow (`tokenUrl: /security/token`,
form-encoded body, response `{access_token, token_type}`). The token carries no
machine-readable expiry in the response body.

Known API quirks that the client must absorb:

- `POST /api/v1/self-service/create/{wallet_type}` and
  `POST /api/v1/self-service/info` take `payload` as a **query** parameter
  (declared `format: binary`), not as a request body.
- `GET /api/v1/self-service/payload/{template_id}/{person_id}` returns an opaque
  binary/string payload with no schema.
- `GET /api/v1/search_persons/{template_id}/{term}` returns
  `list[dict[str, Any]]` — the spec declares free-form objects.
- Mutating pass operations answer `202 Accepted` with a
  `PassOperationResponse`, i.e. they are asynchronous on the server side.

## Architecture

Namespace package `edutap.heidi_api` (PEP 420, `src/` layout), consistent with
`edutap.wallet_google` and `edutap.wallet_apple`. Python 3.12+; tox matrix over
3.12, 3.13 and 3.14.

```
src/edutap/heidi_api/
    __init__.py      # public exports
    settings.py      # HeidiSettings (pydantic-settings, env prefix HEIDI_)
    models.py        # Pydantic v2 models and enums
    exceptions.py    # HeidiError hierarchy
    auth.py          # TokenManager: lazy login, single re-auth on 401
    client.py        # HeidiClient: flat, async
tests/
    data/openapi.json   # checked-in reference copy of the upstream spec
docs/                   # Sphinx + MyST, Diataxis structure
```

Each module has one job: `settings` reads configuration, `models` describes the
wire contract, `auth` owns the token lifecycle, `client` owns transport and
endpoint methods, `exceptions` defines the error surface. `client` depends on
all of them; nothing depends on `client`.

## Models

Hand-written Pydantic v2 models, mirroring the upstream schemas but with
pythonic names and docstrings. The checked-in `openapi.json` is the reference;
a drift test guards it (see *Testing*).

- `WalletType(StrEnum)`: `UNSET`, `APPLE`, `GOOGLE`.
- `PassState(StrEnum)`: values as sent by the API (`"New"`, `"Install pending"`,
  `"Update pending"`, `"Delete pending"`, `"Active"`, `"Inactive"`); member
  names are upper snake case (`INSTALL_PENDING`).
- `PassData`: `pass_id: UUID`, `person_id: str`, `template_id: UUID`,
  `wallet_type: WalletType`, `pass_state: PassState`, `last_update: datetime`,
  `install_link: str | None`.
- `PassTemplate`: `id: UUID`, `title: str`, `wallet_types: list[WalletType]`.
- `PayloadPass`: `wallet_type`, `pass_state`, `install_link: str | None`.
- `PayloadInfo`: `template_display_name: str`, `wallet_types: list[WalletType]`,
  `passes: list[PayloadPass]`.
- `PassOperationResponse`: `pass_id: UUID`, `detail: str`.
- `Token`: `access_token: str`, `token_type: str`.
- `AuthenticatedUser`: `display_name`, `username`, `roles: list[str]`,
  `customer_id: UUID | None`, `customer_display_name: str | None`.
- `ValidationErrorDetail`: `loc: list[str | int]`, `msg: str`, `type: str` —
  used to enrich `HeidiValidationError`.

`CreatePassOperation` stays internal: `create_pass()` takes keyword arguments
and builds the request body itself.

## Client surface

`HeidiClient` is flat: every operation is a method on the client. It is an async
context manager and owns an `httpx.AsyncClient`, which can also be injected.

```python
from edutap.heidi_api import HeidiClient, WalletType

async with HeidiClient() as heidi:
    templates = await heidi.list_pass_templates()
    op = await heidi.create_pass(
        template_id=templates[0].id,
        person_id="12345",
        wallet_type=WalletType.APPLE,
    )
    data = await heidi.get_pass(op.pass_id)
```

| Method | HTTP operation | Returns |
| --- | --- | --- |
| `whoami()` | `GET /security/authenticated` | `AuthenticatedUser` |
| `get_pass(pass_id)` | `GET /api/v1/pass/{pass_id}` | `PassData` |
| `update_pass(pass_id)` | `PUT /api/v1/pass/{pass_id}` | `PassOperationResponse` |
| `delete_pass(pass_id)` | `DELETE /api/v1/pass/{pass_id}` | `PassOperationResponse` |
| `create_pass(template_id, person_id, wallet_type)` | `POST /api/v1/pass` | `PassOperationResponse` |
| `get_passes(template_id, person_id)` | `GET /api/v1/passes/…` | `list[PassData]` |
| `update_passes(template_id, person_id)` | `PUT /api/v1/passes/…` | `PassOperationResponse` |
| `delete_passes(template_id, person_id)` | `DELETE /api/v1/passes/…` | `PassOperationResponse` |
| `list_wallet_types()` | `GET /api/v1/wallet_types` | `list[WalletType]` |
| `list_pass_templates()` | `GET /api/v1/pass_templates` | `list[PassTemplate]` |
| `search_persons(template_id, term)` | `GET /api/v1/search_persons/…` | `list[dict[str, Any]]` |
| `get_self_service_payload(template_id, person_id)` | `GET /api/v1/self-service/payload/…` | `str` |
| `get_self_service_info(payload)` | `POST /api/v1/self-service/info` | `PayloadInfo` |
| `create_pass_from_payload(wallet_type, payload)` | `POST /api/v1/self-service/create/{wallet_type}` | `PassOperationResponse` |

`pass_id`, `template_id` accept `UUID` or `str`; `wallet_type` accepts
`WalletType` or `str`. The opaque self-service payload is typed as `str` and
passed through unchanged as a query parameter.

All requests funnel through one private `_request()` helper that adds the bearer
token, sends the request, maps error statuses to exceptions, and validates the
response into the declared model.

## Configuration and authentication

`HeidiSettings(BaseSettings)` with env prefix `HEIDI_`:

- `base_url: HttpUrl = "https://api.cloud.heidi-pass.com"`
- `username: str`
- `password: SecretStr`
- `timeout: float = 30.0`

`HeidiClient()` builds settings from the environment by default; a
`HeidiSettings` instance or an existing `httpx.AsyncClient` can be passed in.

`TokenManager` fetches the token lazily on the first authenticated call
(`POST /security/token`, `application/x-www-form-urlencoded`, `grant_type=password`)
and caches it. Because the token carries no expiry, expiry is detected
reactively: when an authenticated request answers `401`, the manager discards
the token, re-authenticates **once**, and replays the request. A second `401`
raises `HeidiAuthError`. Concurrent callers serialise re-authentication through
an `anyio.Lock` so only one token request is in flight. Credentials are held as
`SecretStr` and never logged or included in exception messages.

No automatic retries beyond that single re-auth.

## Error handling

```
HeidiError                     # base, carries status_code, request_url, raw body
├── HeidiAuthError             # 401
├── HeidiNotFoundError         # 404
├── HeidiConflictError         # 409 (e.g. update while an operation is pending)
├── HeidiValidationError       # 422, exposes list[ValidationErrorDetail]
├── HeidiRateLimitError        # 429, exposes retry_after if the header is present
└── HeidiServerError           # 5xx
```

Transport-level failures (connect errors, timeouts) propagate as the
corresponding `httpx` exceptions — wrapping them would hide useful detail.

## Testing

Test-driven: every behaviour gets a failing test first.

- **Unit tests** (`make test-local`): `pytest` + `anyio`, all HTTP mocked with
  `respx`. No network. Cover each client method, the token lifecycle
  (lazy fetch, caching, re-auth on 401, failure on second 401), every exception
  mapping, and model parsing of representative payloads.
- **Integration tests** (`make test-integration`): marked
  `@pytest.mark.integration`, skipped unless `HEIDI_USERNAME`/`HEIDI_PASSWORD`
  are set. Read-only operations only (`whoami`, `list_pass_templates`,
  `list_wallet_types`) so a test run never mutates production passes.
- **Spec drift test** (`make test-drift`): fetches the live `openapi.json` and
  diffs it against `tests/data/openapi.json`, reporting added, removed and
  changed operations and schemas. Marked as a network test and excluded from
  `test-local`.

## Tooling

`uv` for environment and dependencies; runtime deps `httpx`, `pydantic`,
`pydantic-settings`, `anyio`; dev extra with `pytest`, `pytest-asyncio`/`anyio`,
`respx`, `ruff`, `ty`, `pdbp`. `ruff` for lint and format, `ty` for type
checking, `prek` as hook runner, `tox` (via `uvx`) for the version matrix.

`Makefile` targets: `lint`, `reformat`, `test-local`, `test-integration`,
`test-drift`.

GitHub Actions CI mirrors local checks: ruff check, ruff format `--check`, ty,
and the tox matrix over supported Python versions.

Documentation with Sphinx + MyST following Diataxis: a tutorial (issue a first
pass), how-tos (configure credentials, handle pending states), reference (the
client API), and an explanation of the asynchronous `202`-based pass lifecycle.
