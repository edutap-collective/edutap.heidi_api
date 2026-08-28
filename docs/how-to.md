# How-to guides

## Configure credentials

Settings are read from the environment with the prefix `HEIDI_`:

| Variable | Default |
| --- | --- |
| `HEIDI_USERNAME` | none |
| `HEIDI_PASSWORD` | none |
| `HEIDI_BASE_URL` | `https://api.cloud.heidi-pass.com` |
| `HEIDI_TIMEOUT` | `30.0` |

`HEIDI_USERNAME` and `HEIDI_PASSWORD` are only needed for the issuer operations and for `get_self_service_payload`. A client built without them can still call `get_self_service_info` and `create_pass_from_payload` — see {doc}`reference` — but raises `HeidiAuthError` if anything else needs a token.

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

## Handle other HEIDI error responses

Every error response HEIDI returns is raised as a subclass of `HeidiError`,
which carries `status_code`, `request_url` and `body`:

| Exception | Status | Notes |
| --- | --- | --- |
| `HeidiAuthError` | 401 | Authentication failed or the token was rejected. |
| `HeidiNotFoundError` | 404 | The pass, template or person does not exist. |
| `HeidiConflictError` | 409 | Another operation on the same pass is still running. |
| `HeidiValidationError` | 422 | The request was rejected as invalid; `errors` holds the parsed detail list. |
| `HeidiRateLimitError` | 429 | Too many requests; upstream declares this on `/security/token`. |
| `HeidiServerError` | 5xx | HEIDI failed to handle the request. |

Catch `HeidiError` itself to handle every case uniformly, or catch a specific
subclass to react to one status code. `HeidiRateLimitError` exposes
`retry_after` — the parsed `Retry-After` header, in seconds, or `None` if
HEIDI did not send one:

The exception message redacts the query string of `request_url`, since the
self-service endpoints carry the opaque payload there. `HeidiError.body` is
not redacted, though: it is the response body HEIDI sent back, verbatim, and
a self-service error response could echo the payload into it. Do not log
`HeidiError.body` verbatim in contexts where that payload must stay
confidential.

```python
import anyio

from edutap.heidi_api import HeidiClient, HeidiRateLimitError

async with HeidiClient() as heidi:
    try:
        await heidi.whoami()
    except HeidiRateLimitError as exc:
        if exc.retry_after is not None:
            await anyio.sleep(exc.retry_after)
        # retry the call
```

## Use the self-service flow

```python
from edutap.heidi_api import HeidiClient, WalletType

async with HeidiClient() as heidi:
    payload = await heidi.get_self_service_payload(template_id, person_id)
    info = await heidi.get_self_service_info(payload)
    if WalletType.GOOGLE in info.wallet_types:
        await heidi.create_pass_from_payload(WalletType.GOOGLE, payload)
```

The payload is opaque — store and forward it unchanged.

`get_self_service_info` and `create_pass_from_payload` need no issuer credentials
— the payload itself is the authorization — so this flow also works from a client built with `HeidiSettings(username=None, password=None)`, e.g. in a self-service frontend that never sees issuer credentials. `get_self_service_payload` still does require credentials.

## Release the package

`.github/workflows/release.yaml` publishes twice, from the same artifact and
never from a developer's machine:

| Trigger | Target | Environment |
| --- | --- | --- |
| Every commit on `main` | `test.pypi.org` | `release-test-pypi` |
| A GitHub Release marked *published* | `pypi.org` | `release-pypi` |

Both uploads use [Trusted Publishing](https://docs.pypi.org/trusted-publishers/),
so there is no API token anywhere in the repository. What authenticates the
upload is the workflow itself, identified by repository, workflow file and
environment.

### One-time setup

Do this once per index, before the first release:

1. On [pypi.org](https://pypi.org/manage/account/publishing/) and again on
   [test.pypi.org](https://test.pypi.org/manage/account/publishing/), add a
   *pending publisher* — the form for a project that does not exist yet; see
   [Creating a PyPI project with a trusted publisher](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/).
   Project name `edutap.heidi_api`, owner `edutap-collective`, repository
   `edutap.heidi_api`, workflow `release.yaml`, environment `release-pypi`
   on pypi.org and `release-test-pypi` on test.pypi.org.
2. In the repository's *Settings → Environments*, create both environments under
   exactly those names. A publisher that names an environment the repository
   does not have will reject the upload, and the error names OIDC rather than
   the missing environment.

### Cutting a release

1. Raise `version` in `pyproject.toml` on a branch and merge it. The commit on
   `main` lands on Test PyPI; install it from there to check the artifact.
2. Tag that commit `vX.Y.Z` and publish a GitHub Release for the tag. Publishing
   — not tagging — is what uploads to pypi.org.

One version means one tag means one commit. Never publish a Release for a tag
that predates this workflow: the run happens at that ref, finds no workflow, and
silently does nothing.
