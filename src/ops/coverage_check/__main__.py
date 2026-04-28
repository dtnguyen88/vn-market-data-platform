"""Coverage check. Reads last 5min of ingest-receipts/, computes coverage% per stream.

Alerts via shared.alerts if any stream has zero recent files (treated as coverage drop).
"""

import json
import os
from datetime import UTC, datetime, timedelta

from shared.alerts import publish_alert

STREAMS = ["ticks", "quotes-l1", "quotes-l2", "indices"]


def main() -> None:
    project_id = os.environ["GCP_PROJECT_ID"]
    env = os.environ.get("ENV", "staging")
    bucket_name = f"vn-market-lake-{env}"

    from google.cloud import storage

    client = storage.Client(project=project_id)
    bucket = client.bucket(bucket_name)

    cutoff = datetime.now(UTC) - timedelta(minutes=5)
    today = datetime.now(UTC).date().isoformat()
    coverage: dict[str, dict] = {}

    for stream in STREAMS:
        prefix = f"_ops/ingest-receipts/{today}/{stream}/"
        blobs = list(bucket.list_blobs(prefix=prefix))
        recent = [
            b for b in blobs if b.time_created and b.time_created.replace(tzinfo=UTC) >= cutoff
        ]
        symbols_seen: set[str] = set()
        for b in recent:
            try:
                rec = json.loads(b.download_as_text().splitlines()[0])
                if "symbol" in rec:
                    symbols_seen.add(rec["symbol"])
            except Exception as exc:
                print(f"receipt parse error for {b.name}: {exc}")
                continue
        coverage[stream] = {"recent_files": len(recent), "unique_symbols": len(symbols_seen)}

    summary = {"env": env, "ts": datetime.now(UTC).isoformat(), "coverage": coverage}
    print(json.dumps(summary))

    # Alert if any stream had zero recent files (treat as coverage drop)
    zero_streams = [s for s, c in coverage.items() if c["recent_files"] == 0]
    if zero_streams:
        try:
            publish_alert(
                project_id=project_id,
                severity="warning",
                name="coverage_drop",
                body=f"streams with 0 recent receipts: {zero_streams}",
                source="coverage-check",
                extra={"streams": zero_streams},
            )
        except Exception as e:
            print(f"alert failed: {e}")


if __name__ == "__main__":
    main()
