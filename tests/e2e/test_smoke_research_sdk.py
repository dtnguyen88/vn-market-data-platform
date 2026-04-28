"""E2E smoke: run vnmarket SDK against staging.

Skipped without GCP_PROJECT_ID + ENV.
"""

import os

import pytest

pytestmark = pytest.mark.e2e

PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
ENV = os.environ.get("ENV")


@pytest.fixture(scope="module")
def project():
    if not PROJECT_ID or not ENV:
        pytest.skip("GCP_PROJECT_ID and ENV must be set for e2e tests")


def test_sdk_quickstart_smoke(project):
    """Mirror notebooks/00-quickstart.ipynb — assert no exceptions."""
    import vnmarket as vm

    client = vm.Client(env=ENV)
    # Just construct + call cheap methods; assert no exceptions
    client.gaps(stream="ticks")
    # Empty result acceptable for a fresh deployment
    df = client.tickers()
    assert df is not None  # may be empty
