"""Integration: publish 100 synthetic ticks → assert GCS landing.

Skipped unless GCP_PROJECT_ID and ENV env vars are set.
"""

import json
import os
import time
from datetime import UTC, date, datetime, timedelta

import pytest

pytestmark = pytest.mark.integration

PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
ENV = os.environ.get("ENV")
SKIP_REASON = "GCP_PROJECT_ID and ENV must be set for integration tests"


@pytest.fixture(scope="module")
def project():
    if not PROJECT_ID or not ENV:
        pytest.skip(SKIP_REASON)
    return PROJECT_ID


def test_pubsub_to_gcs_happy_path(project):
    from google.cloud import pubsub_v1, storage

    bucket_name = f"vn-market-lake-{ENV}"
    publisher = pubsub_v1.PublisherClient()
    topic = publisher.topic_path(project, "market-ticks")

    today = date.today()
    base_ts = datetime.now(UTC) - timedelta(seconds=60)
    n = 100
    for i in range(n):
        ts_ms = int((base_ts + timedelta(seconds=i / 10)).timestamp() * 1000)
        body = {
            "ts_event": (base_ts + timedelta(seconds=i / 10)).isoformat(),
            "ts_received": datetime.now(UTC).isoformat(),
            "symbol": "VNM",
            "asset_class": "equity",
            "exchange": "HOSE",
            "price": 850000 + i,
            "volume": 100,
            "match_type": "continuous",
            "side": "B",
            "trade_id": f"INT-T{ts_ms}-{i}",
            "seq": i,
        }
        future = publisher.publish(
            topic,
            json.dumps(body).encode("utf-8"),
            symbol="VNM",
            asset_class="equity",
            schema_version="1",
            shard="0",
        )
        future.result(timeout=10)

    # Poll GCS for landing
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    prefix = f"raw/ticks/date={today.isoformat()}/asset_class=equity/symbol=VNM/"

    deadline = time.time() + 120
    found_blobs: list = []
    while time.time() < deadline:
        found_blobs = list(bucket.list_blobs(prefix=prefix))
        if found_blobs:
            break
        time.sleep(5)

    assert found_blobs, f"no Parquet files appeared under gs://{bucket_name}/{prefix} within 120s"
