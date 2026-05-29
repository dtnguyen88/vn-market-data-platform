"""End-to-end test for curate_daily_ohlcv on local Parquet fixtures.

No GCS required — uses tmp_path. Proves the vectorized adjustment path
produces correct output through the full read → dedup → adjust → write pipeline.
"""

from datetime import date, timedelta

import polars as pl
import pytest

from curate.streams.daily_ohlcv import curate_daily_ohlcv

pytestmark = pytest.mark.integration


def _write_daily_fixture(path) -> None:
    """5 symbols x 60 days each. Includes 2 duplicate rows to exercise dedup."""
    base = date(2024, 1, 2)
    symbols = ["VNM", "FPT", "HPG", "SSI", "VCB"]
    rows = []
    for s in symbols:
        for d in range(60):
            rows.append(
                {
                    "date": base + timedelta(days=d),
                    "symbol": s,
                    "asset_class": "stock",
                    "exchange": "HOSE",
                    "open": 10_000 + d * 10,
                    "high": 10_100 + d * 10,
                    "low": 9_900 + d * 10,
                    "close": 10_000 + d * 10,
                    "volume": 1_000_000,
                    "value": 10_000_000_000,
                }
            )
    # Duplicates: same (date, symbol) — dedup keeps first.
    rows.append(dict(rows[5]))
    rows.append(dict(rows[120]))
    pl.DataFrame(rows).write_parquet(path)


def _write_corp_actions_fixture(path) -> None:
    """VNM split, HPG stock div, VCB cash div; FPT/SSI have no actions."""
    base = date(2024, 1, 2)
    rows = [
        {
            "ex_date": base + timedelta(days=30),
            "symbol": "VNM",
            "action_type": "split",
            "ratio": 2.0,
            "amount": None,
        },
        {
            "ex_date": base + timedelta(days=20),
            "symbol": "HPG",
            "action_type": "dividend_stock",
            "ratio": 0.1,
            "amount": None,
        },
        {
            "ex_date": base + timedelta(days=45),
            "symbol": "VCB",
            "action_type": "dividend_cash",
            "ratio": None,
            "amount": 500.0,
        },
    ]
    pl.DataFrame(rows, schema_overrides={"amount": pl.Float64, "ratio": pl.Float64}).write_parquet(
        path
    )


@pytest.mark.integration
def test_curate_daily_ohlcv_e2e(tmp_path):
    daily_path = tmp_path / "daily.parquet"
    ca_path = tmp_path / "corp_actions.parquet"
    out_path = tmp_path / "curated.parquet"
    _write_daily_fixture(daily_path)
    _write_corp_actions_fixture(ca_path)

    metrics = curate_daily_ohlcv(str(daily_path), str(ca_path), str(out_path))

    assert metrics["rows_out"] == 5 * 60  # dedup drops the 2 duplicates
    assert metrics["rows_in"] == 5 * 60 + 2

    out = pl.read_parquet(out_path)
    assert "adj_close" in out.columns
    assert out["adj_close"].null_count() == 0
    assert (out["adj_close"] > 0).all()

    # FPT/SSI no actions → adj_close == close.
    for sym in ("FPT", "SSI"):
        sub = out.filter(pl.col("symbol") == sym).sort("date")
        assert sub["adj_close"].to_list() == sub["close"].to_list()

    # VNM split at day 30 (ratio 2.0): rows before ex_date get adj = close * 0.5.
    vnm = out.filter(pl.col("symbol") == "VNM").sort("date")
    pre_split = vnm.filter(pl.col("date") < date(2024, 2, 1))
    post_split = vnm.filter(pl.col("date") >= date(2024, 2, 1))
    pre_pairs = list(
        zip(pre_split["close"].to_list(), pre_split["adj_close"].to_list(), strict=True)
    )
    for close, adj in pre_pairs:
        assert abs(adj - close // 2) <= 1, (close, adj)
    # Post-split: adj == close.
    assert post_split["adj_close"].to_list() == post_split["close"].to_list()


@pytest.mark.integration
def test_curate_daily_ohlcv_empty_corp_actions(tmp_path):
    """When corp_actions file is missing/empty, adj_close == close."""
    daily_path = tmp_path / "daily.parquet"
    ca_path = tmp_path / "corp_actions_missing.parquet"  # not created
    out_path = tmp_path / "curated.parquet"
    _write_daily_fixture(daily_path)

    metrics = curate_daily_ohlcv(str(daily_path), str(ca_path), str(out_path))
    assert metrics["rows_out"] == 5 * 60

    out = pl.read_parquet(out_path)
    assert out["adj_close"].to_list() == out["close"].to_list()
