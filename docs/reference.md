# Reference

`HeidiClient` exposes fourteen methods, one per HEIDI Cloud API operation.
Every method is a coroutine.
Every method that mutates a pass returns a `PassOperationResponse` and does not wait for the change to take effect; see {doc}`explanation` for what that means.

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

## Models and exceptions

```{eval-rst}
.. automodule:: edutap.heidi_api.models
   :members:

.. automodule:: edutap.heidi_api.exceptions
   :members:
```
