"""Smoke tests for the package itself."""


def test_package_exposes_a_version() -> None:
    import edutap.heidi_api

    assert isinstance(edutap.heidi_api.__version__, str)
    assert edutap.heidi_api.__version__
