"""Unit tests for shared.alerts.publish_alert."""

from unittest.mock import MagicMock, patch

import pytest
from shared.alerts import publish_alert


@pytest.mark.unit
@patch("shared.alerts.pubsub_v1.PublisherClient")
def test_publish_alert_basic(mock_cls):
    client = MagicMock()
    client.topic_path.return_value = "projects/p/topics/platform-alerts"
    future = MagicMock()
    future.result.return_value = "msg-123"
    client.publish.return_value = future
    mock_cls.return_value = client

    result = publish_alert(
        project_id="p",
        severity="warning",
        name="coverage_drop",
        body="VNM coverage 80%",
        scope="ticks",
        source="intraday-coverage-check",
    )
    assert result == "msg-123"
    client.publish.assert_called_once()
    args, kwargs = client.publish.call_args
    assert args[0] == "projects/p/topics/platform-alerts"
    assert kwargs["severity"] == "warning"
    assert kwargs["alert_name"] == "coverage_drop"
    assert kwargs["scope"] == "ticks"
    assert kwargs["source"] == "intraday-coverage-check"


@pytest.mark.unit
@patch("shared.alerts.pubsub_v1.PublisherClient")
def test_publish_alert_minimal(mock_cls):
    client = MagicMock()
    client.topic_path.return_value = "projects/p/topics/platform-alerts"
    future = MagicMock()
    future.result.return_value = "msg-1"
    client.publish.return_value = future
    mock_cls.return_value = client

    publish_alert(project_id="p", severity="info", name="eod_done", body="ok")
    args, kwargs = client.publish.call_args
    assert "scope" not in kwargs
    assert "source" not in kwargs
    assert kwargs["severity"] == "info"
    assert kwargs["alert_name"] == "eod_done"
