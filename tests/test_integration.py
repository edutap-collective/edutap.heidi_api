"""Read-only smoke tests against the live HEIDI service.

Skipped unless ``HEIDI_USERNAME`` and ``HEIDI_PASSWORD`` are set. These tests
never mutate data: they may run against a production installation.
"""

import os

import pytest

from edutap.heidi_api import AuthenticatedUser, HeidiClient, PassTemplate, WalletType

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.integration,
    pytest.mark.skipif(
        not (os.environ.get("HEIDI_USERNAME") and os.environ.get("HEIDI_PASSWORD")),
        reason="HEIDI_USERNAME and HEIDI_PASSWORD are not set",
    ),
]


async def test_whoami_returns_the_configured_user() -> None:
    async with HeidiClient() as heidi:
        user = await heidi.whoami()

    assert isinstance(user, AuthenticatedUser)
    assert user.username == os.environ["HEIDI_USERNAME"]


async def test_wallet_types_are_known_members() -> None:
    async with HeidiClient() as heidi:
        wallet_types = await heidi.list_wallet_types()

    assert all(isinstance(item, WalletType) for item in wallet_types)


async def test_pass_templates_parse() -> None:
    async with HeidiClient() as heidi:
        templates = await heidi.list_pass_templates()

    assert all(isinstance(item, PassTemplate) for item in templates)


async def test_one_client_serves_several_calls() -> None:
    async with HeidiClient() as heidi:
        await heidi.whoami()
        await heidi.list_pass_templates()
        user = await heidi.whoami()

    assert user.username == os.environ["HEIDI_USERNAME"]
