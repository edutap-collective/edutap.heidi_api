"""Guard the hand-written models against upstream API changes.

This test talks to the live HEIDI service and is therefore excluded from
``make test-local``. Run it with ``make test-drift``.
"""

import json
from pathlib import Path

import httpx
import pytest

pytestmark = [pytest.mark.anyio, pytest.mark.drift]

SPEC_URL = "https://api.cloud.heidi-pass.com/openapi.json"
REFERENCE = Path(__file__).parent / "data" / "openapi.json"
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def _operations(spec: dict) -> set[tuple[str, str]]:
    """Return the set of (method, path) pairs a spec declares."""
    return {
        (method.upper(), path)
        for path, operations in spec["paths"].items()
        for method in operations
        if method in HTTP_METHODS
    }


@pytest.fixture
def reference_spec() -> dict:
    return json.loads(REFERENCE.read_text())


@pytest.fixture
async def live_spec() -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(SPEC_URL)
    response.raise_for_status()
    return response.json()


async def test_no_operations_were_added_or_removed(
    live_spec: dict, reference_spec: dict
) -> None:
    live = _operations(live_spec)
    reference = _operations(reference_spec)

    assert live - reference == set(), "HEIDI added operations"
    assert reference - live == set(), "HEIDI removed operations"


async def test_schemas_are_unchanged(live_spec: dict, reference_spec: dict) -> None:
    live = live_spec["components"]["schemas"]
    reference = reference_spec["components"]["schemas"]

    assert set(live) == set(reference), "the set of schemas changed"
    changed = [name for name in reference if live[name] != reference[name]]
    assert changed == [], f"schemas changed upstream: {changed}"
