# Design decisions behind the HEIDI client

## About asynchronous pass operations

Every method that mutates a pass — `create_pass`, `update_pass`, `delete_pass` and their plural counterparts — answers `202 Accepted`.
HEIDI acknowledges the request and carries it out later, not `200 OK` with the finished result.
The response body is a `PassOperationResponse`: a `pass_id` and a human-readable `detail`, nothing about the outcome.

This shape follows from how a wallet pass actually gets installed.
Creating or changing a pass means pushing an update through Apple's or Google's wallet infrastructure, which HEIDI does not control and cannot make synchronous.
Answering `202` is HEIDI being honest about that: the request is accepted, not completed.

The pass reflects this in its `pass_state`.
Immediately after `create_pass` the state is `Install pending`; after `update_pass` it is `Update pending`; after `delete_pass` it is `Delete pending`.
HEIDI moves the pass to `Active` or `Inactive` once the wallet provider confirms the change, and to `Inactive` again if the change fails.
There is no push notification for this — the client finds out by calling `get_pass` again.

For callers this means the result of a mutation is eventually consistent, not immediate.
Code that needs the final state polls `get_pass` until `pass_state` leaves the pending value, as the tutorial does.
Code that only needs to know the request was accepted can stop at the `PassOperationResponse` and ignore the rest.

A second consequence is `409 Conflict`.
While a pass is in a pending state, HEIDI rejects further mutations on it — the previous operation has not settled yet.
`HeidiConflictError` surfaces this; see {doc}`how-to` for handling it.

## About reactive re-authentication

`HeidiClient` does not track when its access token expires.
It cannot: the `POST /security/token` response carries an `access_token` and a `token_type`, nothing else, no `expires_in` or issue time to schedule a refresh against.

So the client treats expiry as something the server reports, not something it predicts.
Every request goes out with the current token.
If the server answers `401 Unauthorized`, the client assumes the token has expired, fetches a new one, and replays the request exactly once.
A `401` on that replay is not treated as another expired token — it means the credentials themselves are wrong — and surfaces as `HeidiAuthError`.

This keeps the client simple: there is no background timer, no clock skew to account for, and no state beyond the token itself.
It also means a token lives exactly as long as the server is willing to accept it, whatever that turns out to be in practice.
The trade-off is one wasted round trip per expiry, the request that comes back `401` before the refresh — a cost worth paying for not having to guess a lifetime the API does not advertise.

Concurrent requests share this behavior through a single `TokenManager`.
If several requests hit `401` around the same time, only the first triggers an actual refresh; the others see the already-refreshed token and skip straight to replaying.
