"""Unit tests for vnmarket.Client surface — minimal smoke (no real GCS)."""

import pytest
from vnmarket import Client


@pytest.mark.unit
def test_client_default_project_from_env():
    c = Client(env="staging")
    assert c.project == "vn-market-platform-staging"
    assert c.bucket == "vn-market-lake-staging"


@pytest.mark.unit
def test_client_explicit_project():
    c = Client(project="custom-proj", env="prod")
    assert c.project == "custom-proj"
    assert c.bucket == "vn-market-lake-prod"


@pytest.mark.unit
def test_gcs_glob_construction():
    c = Client(env="staging")
    assert c._gcs_glob("curated/ticks/**") == "gs://vn-market-lake-staging/curated/ticks/**"
