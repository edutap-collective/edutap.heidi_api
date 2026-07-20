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
