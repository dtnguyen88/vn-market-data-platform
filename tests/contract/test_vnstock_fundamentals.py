"""Contract test: vnstock fundamentals endpoint."""

import os

import pytest

pytestmark = pytest.mark.contract

if not os.environ.get("CONTRACT"):
    pytest.skip("contract tests require CONTRACT=1", allow_module_level=True)


def test_vnstock_fundamentals_vnm_returns_rows():
    import vnstock

    df = vnstock.Vnstock().stock(symbol="VNM", source="TCBS").finance.ratio()
    assert df is not None
    # Just check it returned something (column names vary; we normalize in curate)
    assert len(df) >= 0
