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
from edutap.heidi_api import HeidiClient, WalletType

async with HeidiClient() as heidi:
    payload = await heidi.get_self_service_payload(template_id, person_id)
    info = await heidi.get_self_service_info(payload)
    if WalletType.GOOGLE in info.wallet_types:
        await heidi.create_pass_from_payload(WalletType.GOOGLE, payload)
```

The payload is opaque — store and forward it unchanged.
