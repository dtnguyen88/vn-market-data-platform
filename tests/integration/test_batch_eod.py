"""Integration: trigger batch-ingester-eod for a known historical date → assert GCS landing.

Skipped unless GCP_PROJECT_ID and ENV env vars are set.

Usage:
    GCP_PROJECT_ID=vn-market-platform-staging ENV=staging \\
        uv run pytest tests/integration/test_batch_eod.py -v -m integration
"""

import os
import time
from datetime import date

import pytest

pytestmark = pytest.mark.integration

PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
ENV = os.environ.get("ENV")
SKIP_REASON = "GCP_PROJECT_ID and ENV must be set for integration tests"

# Known historical date with reliable vnstock coverage. Mid-January = active trading;
# avoid Tet holidays (late Jan / early Feb varies year-by-year).
TARGET_DATE = date(2024, 1, 15)


@pytest.fixture(scope="module")
def project():
    if not PROJECT_ID or not ENV:
        pytest.skip(SKIP_REASON)
    return PROJECT_ID


def test_eod_job_lands_daily_files(project):
    """Trigger batch-ingester-eod, wait, assert daily Parquet files exist."""
    from google.cloud import run_v2, storage

    # 1. Trigger Cloud Run Job execution with TARGET_DATE override
    jobs = run_v2.JobsClient()
    name = f"projects/{project}/locations/asia-southeast1/jobs/batch-ingester-eod"
    overrides = run_v2.RunJobRequest.Overrides(
        container_overrides=[
            run_v2.RunJobRequest.Overrides.ContainerOverride(
                env=[
                    run_v2.EnvVar(name="TARGET_DATE", value=TARGET_DATE.isoformat()),
                    run_v2.EnvVar(name="ENV", value=ENV),
                    run_v2.EnvVar(name="GCP_PROJECT_ID", value=project),
                ],
            ),
        ],
    )
    op = jobs.run_job(request=run_v2.RunJobRequest(name=name, overrides=overrides))

    # 2. Wait for execution to complete (poll up to 35 min)
    deadline = time.time() + 35 * 60
    while time.time() < deadline:
        if op.done():
            break
        time.sleep(15)
    else:
        pytest.fail("execution did not complete within 35 min")

    result = op.result()  # raises on error
    assert result is not None

    # 3. Assert daily files appear in GCS
    bucket_name = f"vn-market-lake-{ENV}"
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    prefix = f"raw/daily-ohlcv/year={TARGET_DATE.year}/date={TARGET_DATE.isoformat()}/"

    blobs = list(bucket.list_blobs(prefix=prefix))
    assert blobs, f"no Parquet files under gs://{bucket_name}/{prefix}"
    # At minimum we expect the dev-fallback 10 symbols (when reference snapshot absent).
    # If reference job has run, this could be 1500+. Lower bound is conservative.
    assert len(blobs) >= 5, f"expected >=5 files, got {len(blobs)}"

    # 4. Spot-check: every file is non-empty
    for blob in blobs:
        assert blob.size > 0, f"empty file at {blob.name}"


def test_eod_idempotent_rerun(project):
    """Re-running for the same date should overwrite, not duplicate, partition contents."""
    pytest.skip("requires successful first run; combine into chained test or run manually")
