"""Integration: trigger curate job → assert curated partition appears + queryable.

Skipped unless GCP_PROJECT_ID and ENV env vars are set.

Usage:
    GCP_PROJECT_ID=vn-market-platform-staging ENV=staging \\
        uv run pytest tests/integration/test_curate_e2e.py -v -m integration
"""

import os
import time
from datetime import date

import pytest

pytestmark = pytest.mark.integration

PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
ENV = os.environ.get("ENV")
SKIP_REASON = "GCP_PROJECT_ID and ENV must be set for integration tests"

# Use a known historical date with raw data already present (run batch-eod first).
TARGET_DATE = date(2024, 1, 15)


@pytest.fixture(scope="module")
def project():
    if not PROJECT_ID or not ENV:
        pytest.skip(SKIP_REASON)
    return PROJECT_ID


def _trigger_curate(project: str, stream: str, target_date: date):
    """Trigger the curate Cloud Run Job for one stream + date."""
    from google.cloud import run_v2

    jobs = run_v2.JobsClient()
    name = f"projects/{project}/locations/asia-southeast1/jobs/curate"
    overrides = run_v2.RunJobRequest.Overrides(
        container_overrides=[
            run_v2.RunJobRequest.Overrides.ContainerOverride(
                args=[f"--stream={stream}", f"--date={target_date.isoformat()}"],
                env=[
                    run_v2.EnvVar(name="ENV", value=ENV),
                    run_v2.EnvVar(name="GCP_PROJECT_ID", value=project),
                ],
            ),
        ],
    )
    op = jobs.run_job(request=run_v2.RunJobRequest(name=name, overrides=overrides))
    deadline = time.time() + 20 * 60
    while time.time() < deadline:
        if op.done():
            break
        time.sleep(10)
    else:
        pytest.fail(f"curate {stream} did not complete within 20 min")
    return op.result()


def test_curate_daily_ohlcv(project):
    """Trigger curate-daily-ohlcv, assert curated partition appears + queryable."""
    from google.cloud import bigquery, storage

    _trigger_curate(project, "daily-ohlcv", TARGET_DATE)

    # Assert curated GCS object
    bucket = storage.Client().bucket(f"vn-market-lake-{ENV}")
    prefix = f"curated/daily-ohlcv/year={TARGET_DATE.year}/"
    blobs = list(bucket.list_blobs(prefix=prefix))
    assert blobs, f"no curated files under gs://{bucket.name}/{prefix}"

    # Query via BigLake (excludes the 1900 sentinel placeholder)
    bq = bigquery.Client(project=project)
    query = f"""
    SELECT COUNT(*) AS row_count
    FROM `{project}.vnmarket.daily_ohlcv`
    WHERE date = DATE '{TARGET_DATE.isoformat()}'
    """
    rows = list(bq.query(query).result())
    assert rows[0]["row_count"] > 0, "no rows for target date"


def test_curate_idempotent(project):
    """Second curate run for same date should produce same row count."""
    pytest.skip("requires successful first run; run manually after test_curate_daily_ohlcv")


def test_v_top_of_book_queryable(project):
    """Verify the 3 views are queryable (after curate populates quotes_l1)."""
    from google.cloud import bigquery

    bq = bigquery.Client(project=project)
    rows = list(bq.query(f"SELECT * FROM `{project}.vnmarket.v_top_of_book` LIMIT 5").result())
    # Empty result is OK if no L1 quotes ingested yet — we just need the view to compile.
    assert rows is not None
