"""Contract test: vnstock TCBS daily endpoint returns expected shape.

Skipped unless --run-contract is passed (or env CONTRACT=1).
"""

import os

import pytest

pytestmark = pytest.mark.contract

if not os.environ.get("CONTRACT"):
    pytest.skip("contract tests require CONTRACT=1", allow_module_level=True)


def test_vnstock_daily_vnm_returns_rows():
    import vnstock

    df = (
        vnstock.Vnstock()
        .stock(symbol="VNM", source="TCBS")
        .quote.history(
            start="2024-01-02",
            end="2024-01-31",
            interval="1D",
        )
    )
    assert df is not None
    assert len(df) > 0
    expected_cols = {"time", "open", "high", "low", "close", "volume"}
    assert expected_cols <= set(df.columns)
