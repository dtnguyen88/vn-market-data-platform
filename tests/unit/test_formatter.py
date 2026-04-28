"""Unit tests for alerter.formatter."""

import pytest
from alerter.formatter import _escape, _logs_url, format_alert


@pytest.mark.unit
def test_format_critical_basic():
    msg = format_alert("critical", "publisher_dead", "shard 0 heartbeat absent >90s")
    assert msg.startswith("[CRIT] *publisher\\_dead*")
    assert "shard 0 heartbeat absent" in msg


@pytest.mark.unit
def test_format_with_source_and_extra():
    msg = format_alert(
        "warning",
        "coverage_drop",
        "VNM coverage 80%",
        source="intraday-coverage-check",
        extra={"shard": "1", "stream": "ticks"},
    )
    assert "[WARN]" in msg
    assert "source: `intraday-coverage-check`" in msg
    assert "shard: `1`" in msg
    assert "stream: `ticks`" in msg


@pytest.mark.unit
def test_format_with_log_link():
    msg = format_alert(
        "error",
        "ingest_failure",
        "writer 2 crashed",
        project_id="vn-market-platform-staging",
    )
    assert "[Logs](" in msg
    assert "vn-market-platform-staging" in msg


@pytest.mark.unit
def test_unknown_severity_falls_back():
    msg = format_alert("notice", "test", "body")
    assert msg.startswith("[NOTICE]")


@pytest.mark.unit
def test_escape_handles_markdown_chars():
    assert _escape("a_b*c`d[e") == "a\\_b\\*c\\`d\\[e"


@pytest.mark.unit
def test_logs_url_contains_project_and_name():
    url = _logs_url("vn-market-platform-staging", "publisher_dead")
    assert "vn-market-platform-staging" in url
    assert "publisher_dead" in url
    assert url.startswith("https://console.cloud.google.com/logs/query")
