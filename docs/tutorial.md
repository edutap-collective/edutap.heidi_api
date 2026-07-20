# Issue your first pass

This tutorial creates a wallet pass for one person and waits until HEIDI
reports it as installed.

## Prerequisites

Install the package and set your credentials. The package is not published
to PyPI yet, so install it from the source repository:

```console
uv pip install git+https://github.com/edutap-eu/edutap.heidi_api
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
