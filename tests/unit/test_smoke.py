"""Smoke test — proves the test runner is wired up."""
import pytest


@pytest.mark.unit
def test_python_version_is_312():
    import sys
    assert sys.version_info[:2] == (3, 12)


@pytest.mark.unit
def test_shared_package_importable():
    import shared  # noqa: F401
