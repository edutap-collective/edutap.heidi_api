# edutap.heidi_api

Pythonic async client for the [HEIDI Cloud Service](https://api.cloud.heidi-pass.com/docs) API.

## Installation

```console
uv pip install edutap.heidi_api
```

Every commit on `main` also publishes to Test PyPI, so an unreleased state can be
installed without a git reference:

```console
uv pip install --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ edutap.heidi_api
```

The second index is not optional: Test PyPI does not carry `httpx`, `pydantic` and
the rest, so a resolver pointed only at it fails on the dependencies rather than on
this package.

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
git clone https://github.com/edutap-collective/edutap.heidi_api
cd edutap.heidi_api
make install
make lint
make test-local
```

## Releasing

See [Release the package](docs/how-to.md#release-the-package).
