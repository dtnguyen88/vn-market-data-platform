"""vnmarket.Client — canonical read-path for VN market data.

Reads curated Parquet from GCS via pyarrow.dataset, falls back to BigQuery for
sql() and ad-hoc queries. Local cache via ParquetCache. Gap-aware via gaps module.
"""

from __future__ import annotations

from datetime import date

import polars as pl

from .cache import ParquetCache
from .gaps import load_gaps


class Client:
    """Top-level SDK entrypoint.

    Examples:
        c = vnmarket.Client(project="vn-market-platform-staging", env="staging")
        df = c.daily(["VNM"], "2024-01-01", "2024-12-31")
        ticks = c.ticks("VNM", "2024-01-15").collect()
        gaps = c.gaps(stream="ticks")
    """

    def __init__(self, project: str | None = None, env: str = "staging"):
        self.project = project or f"vn-market-platform-{env}"
        self.env = env
        self.bucket = f"vn-market-lake-{env}"
        self._cache = ParquetCache()

    def _gcs_glob(self, path_within_bucket: str) -> str:
        return f"gs://{self.bucket}/{path_within_bucket.lstrip('/')}"

    def daily(self, symbols: list[str], start: str | date, end: str | date) -> pl.DataFrame:
        """Daily OHLCV via BigQuery (handles both raw and curated layouts).

        Reading via BQ is faster than scanning thousands of small parquets when
        the lake holds per-day partitions; the external table fans out the read.
        """
        sd = date.fromisoformat(start) if isinstance(start, str) else start
        ed = date.fromisoformat(end) if isinstance(end, str) else end
        sym_list = ", ".join(f"'{s}'" for s in symbols)
        query = (
            f"SELECT date, symbol, asset_class, exchange, open, high, low, close, "  # noqa: S608
            f"volume, value FROM `{self.project}.vnmarket.daily_ohlcv` "
            f"WHERE date BETWEEN DATE('{sd.isoformat()}') AND DATE('{ed.isoformat()}') "
            f"AND symbol IN ({sym_list}) "
            f"ORDER BY symbol, date"
        )
        return self.sql(query)

    def ticks(self, symbol: str, on_date: str | date) -> pl.LazyFrame:
        """Lazy frame of ticks for one symbol on one date."""
        d = date.fromisoformat(on_date) if isinstance(on_date, str) else on_date
        uri = self._gcs_glob(
            f"curated/ticks/date={d.isoformat()}/asset_class=*/symbol={symbol}/**/*.parquet"
        )
        return pl.scan_parquet(uri)

    def l2_at(self, symbol: str, ts: str) -> dict:
        """Snapshot of the most recent L2 quote at-or-before `ts`.

        Returns {bid_px[], bid_sz[], ask_px[], ask_sz[]}.
        """
        d = ts[:10]
        uri = self._gcs_glob(
            f"curated/quotes-l2/date={d}/asset_class=*/symbol={symbol}/**/*.parquet"
        )
        try:
            df = (
                pl.scan_parquet(uri)
                .filter(pl.col("ts_event") <= ts)
                .sort("ts_event")
                .last()
                .collect()
            )
        except Exception:
            return {"bid_px": [], "bid_sz": [], "ask_px": [], "ask_sz": []}
        if df.height == 0:
            return {"bid_px": [], "bid_sz": [], "ask_px": [], "ask_sz": []}
        row = df.to_dicts()[0]
        return {
            "bid_px": [row.get(f"bid_px_{i}") for i in range(1, 11)],
            "bid_sz": [row.get(f"bid_sz_{i}") for i in range(1, 11)],
            "ask_px": [row.get(f"ask_px_{i}") for i in range(1, 11)],
            "ask_sz": [row.get(f"ask_sz_{i}") for i in range(1, 11)],
        }

    def index(
        self, code: str, start: str | date, end: str | date, daily: bool = False
    ) -> pl.DataFrame:
        """Index values. `daily=False` returns intraday; `daily=True` aggregated to daily."""
        sd = date.fromisoformat(start) if isinstance(start, str) else start
        ed = date.fromisoformat(end) if isinstance(end, str) else end
        uri = self._gcs_glob("curated/indices/**/*.parquet")
        try:
            lf = pl.scan_parquet(uri).filter(
                (pl.col("index_code") == code)
                & (pl.col("ts_event") >= sd.isoformat())
                & (pl.col("ts_event") <= f"{ed.isoformat()}T23:59:59")
            )
            if daily:
                lf = lf.group_by([pl.col("ts_event").dt.date().alias("date"), "index_code"]).agg(
                    pl.col("value").last().alias("value"),
                    pl.col("change").last().alias("change"),
                    pl.col("change_pct").last().alias("change_pct"),
                )
            return lf.collect()
        except Exception:
            return pl.DataFrame()

    def factors(self, start: str | date, end: str | date) -> pl.DataFrame:
        """Daily factors (close, adj_close, returns) — calls v_daily_factors via BQ."""
        sd = date.fromisoformat(start) if isinstance(start, str) else start
        ed = date.fromisoformat(end) if isinstance(end, str) else end
        query = (
            f"SELECT * FROM `{self.project}.vnmarket.v_daily_factors` "  # noqa: S608
            f"WHERE date BETWEEN '{sd.isoformat()}' AND '{ed.isoformat()}'"
        )
        return self.sql(query)

    def sql(self, query: str) -> pl.DataFrame:
        """Execute SQL via BigQuery and return as Polars DataFrame."""
        from google.cloud import bigquery

        client = bigquery.Client(project=self.project)
        rows = list(client.query(query).result())
        if not rows:
            return pl.DataFrame()
        return pl.from_dicts([dict(r) for r in rows])

    def tickers(self) -> pl.DataFrame:
        """Latest ticker master snapshot."""
        uri = self._gcs_glob("curated/reference/tickers/**/*.parquet")
        try:
            return pl.scan_parquet(uri).collect()
        except Exception:
            return pl.DataFrame()

    def gaps(self, stream: str = "ticks") -> list[dict]:
        """Permanent gaps for a stream. Reads _ops/permanent-gaps/{stream}.jsonl."""
        return load_gaps(self.project, self.env, stream)
