"""Shared pytest fixtures."""

import pytest


@pytest.fixture
def anyio_backend() -> str:
    """Run every anyio test on asyncio only, not on trio."""
    return "asyncio"
