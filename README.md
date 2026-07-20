# edutap.heidi_api

Pythonic async client for the [HEIDI Cloud Service](https://api.cloud.heidi-pass.com/docs) API.

## Installation

The package is not published to PyPI yet. Install it straight from the
source repository:

```console
uv pip install git+https://github.com/edutap-eu/edutap.heidi_api
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

Clone the repository and install it in editable mode with the development
extras:

```console
git clone https://github.com/edutap-eu/edutap.heidi_api
cd edutap.heidi_api
make install
make lint
make test-local
```
