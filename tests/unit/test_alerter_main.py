"""Unit tests for alerter._parse_payload (pure function, no I/O)."""

import os

# Must be set before importing __main__ which reads os.environ["GCP_PROJECT_ID"] at module load.
os.environ.setdefault("GCP_PROJECT_ID", "test-project")

import pytest  # noqa: E402
from alerter.__main__ import _parse_payload  # noqa: E402


@pytest.mark.unit
def test_parse_json_payload():
    body = '{"name":"publisher_dead","severity":"critical","body":"shard 0 down"}'
    out = _parse_payload(body, {})
    assert out["name"] == "publisher_dead"
    assert out["severity"] == "critical"
    assert out["body"] == "shard 0 down"


@pytest.mark.unit
def test_parse_plain_string_with_attrs():
    out = _parse_payload(
        "eod-pipeline-success",
        {
            "severity": "info",
            "source": "eod-pipeline",
            "alert_name": "eod_complete",
        },
    )
    assert out["name"] == "eod_complete"
    assert out["severity"] == "info"
    assert out["source"] == "eod-pipeline"


@pytest.mark.unit
def test_parse_attrs_fallback_when_payload_keys_missing():
    body = '{"body":"some message"}'
    out = _parse_payload(
        body,
        {"alert_name": "a", "severity": "warning", "source": "s"},
    )
    assert out["name"] == "a"
    assert out["severity"] == "warning"
    assert out["source"] == "s"
    assert out["body"] == "some message"
