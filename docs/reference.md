# Reference

`HeidiClient` exposes fourteen methods, one per HEIDI Cloud API operation.
Every method is a coroutine.
Every method that mutates a pass returns a `PassOperationResponse` and does not wait for the change to take effect; see {doc}`explanation` for what that means.

## Constructing and closing the client

```python
HeidiClient(
    settings: HeidiSettings | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> HeidiClient
```

Both arguments are optional and keyword-or-positional.

- `settings` — a `HeidiSettings` instance. If omitted, `HeidiClient` builds one itself, which reads credentials and configuration from the environment (and a `.env` file); see {doc}`how-to`. `username`/`password` are optional — a client built from settings without them can still call the two unauthenticated self-service methods described below.
- `http_client` — an `httpx.AsyncClient` to send requests through. If omitted, `HeidiClient` creates its own, using `settings.base_url` and `settings.timeout`. Pass one in when the surrounding application already manages a connection pool — it **must** already carry a `base_url` (e.g. `httpx.AsyncClient(base_url=settings.base_url)`), since every request `HeidiClient` sends is relative; a client without one is rejected with a `ValueError` at construction time.

`HeidiClient` implements the async context manager protocol; `__aenter__` returns `self`, and `__aexit__` calls `aclose()`. Used without the context manager, call `aclose()` explicitly when done:

```python
await heidi.aclose()
```

`aclose()` closes the underlying `httpx.AsyncClient` — but only if `HeidiClient` created it itself. An `http_client` passed in is borrowed, not owned: `aclose()` leaves it open for the caller to reuse or close.

## Client methods

| Method | HTTP operation |
| --- | --- |
| `whoami() -> AuthenticatedUser` | `GET /security/authenticated` |
| `get_pass(pass_id: UUID \| str) -> PassData` | `GET /api/v1/pass/{pass_id}` |
| `update_pass(pass_id: UUID \| str) -> PassOperationResponse` | `PUT /api/v1/pass/{pass_id}` |
| `delete_pass(pass_id: UUID \| str) -> PassOperationResponse` | `DELETE /api/v1/pass/{pass_id}` |
| `create_pass(*, template_id: UUID \| str, person_id: str, wallet_type: WalletType \| str) -> PassOperationResponse` | `POST /api/v1/pass` |
| `get_passes(template_id: UUID \| str, person_id: str) -> list[PassData]` | `GET /api/v1/passes/{template_id}/{person_id}` |
| `update_passes(template_id: UUID \| str, person_id: str) -> PassOperationResponse` | `PUT /api/v1/passes/{template_id}/{person_id}` |
| `delete_passes(template_id: UUID \| str, person_id: str) -> PassOperationResponse` | `DELETE /api/v1/passes/{template_id}/{person_id}` |
| `list_wallet_types() -> list[WalletType]` | `GET /api/v1/wallet_types` |
| `list_pass_templates() -> list[PassTemplate]` | `GET /api/v1/pass_templates` |
| `search_persons(template_id: UUID \| str, term: str) -> list[dict[str, Any]]` | `GET /api/v1/search_persons/{template_id}/{term}` |
| `get_self_service_payload(template_id: UUID \| str, person_id: str) -> str` | `GET /api/v1/self-service/payload/{template_id}/{person_id}` |
| `get_self_service_info(payload: str) -> PayloadInfo` | `POST /api/v1/self-service/info` |
| `create_pass_from_payload(wallet_type: WalletType \| str, payload: str) -> PassOperationResponse` | `POST /api/v1/self-service/create/{wallet_type}` |

`create_pass` takes its three arguments as keyword-only.
`get_pass`, `update_pass` and `delete_pass` accept a `pass_id` on its own; the other pass-plural methods identify a person's passes for one template by `template_id` and `person_id` together.
`search_persons` returns raw dictionaries: the HEIDI API declares this endpoint's response as a free-form object.
Every `pass_id`/`template_id` is validated as a UUID and rejected otherwise — this also rejects path-traversal or query-injection strings before they ever reach the network.

### Authentication

Twelve of the fourteen operations require issuer credentials (`HeidiSettings.username`/`password`) and send a bearer token obtained via the OAuth2 password grant. `get_self_service_info` and `create_pass_from_payload` are the exception: the upstream spec declares no security requirement for them, so `HeidiClient` sends them with no `Authorization` header and without fetching a token — the opaque payload from `get_self_service_payload` is itself the authorization. `get_self_service_payload` itself remains authenticated.

This means a client built from settings with no `username`/`password` can still call `get_self_service_info` and `create_pass_from_payload`. Calling any of the other twelve methods on such a client raises `HeidiAuthError` naming the missing configuration.

## Models and exceptions

```{eval-rst}
.. automodule:: edutap.heidi_api.models
   :members:

.. automodule:: edutap.heidi_api.exceptions
   :members:
```
