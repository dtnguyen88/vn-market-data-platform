"""Unit tests for PubsubPublisher — uses mocks, no real Pub/Sub."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from publisher.pubsub_publisher import PubsubPublisher
from shared.schemas import Exchange, IndexValue


@pytest.fixture
def sample_index():
    return IndexValue(
        ts_event=datetime(2026, 4, 27, 9, 0, 0, tzinfo=UTC),
        ts_received=datetime(2026, 4, 27, 9, 0, 1, tzinfo=UTC),
        index_code="VNINDEX",
        exchange=Exchange.HOSE,
        value=1234.56,
        change=12.34,
        change_pct=1.01,
        total_volume=50_000_000,
        total_value=1_500_000_000_000,
        advance_count=220,
        decline_count=180,
        unchanged_count=50,
    )


@pytest.mark.unit
@patch("publisher.pubsub_publisher.pubsub_v1.PublisherClient")
def test_publish_serializes_and_calls_client(mock_client_cls, sample_index):
    mock_client = MagicMock()
    mock_client.topic_path.return_value = "projects/p/topics/market-indices"
    mock_future = MagicMock()
    mock_client.publish.return_value = mock_future
    mock_client_cls.return_value = mock_client

    p = PubsubPublisher("p", "market-indices")
    p.publish(sample_index, attributes={"symbol": "VNINDEX", "asset_class": "index"})

    assert mock_client.publish.call_count == 1
    args, kwargs = mock_client.publish.call_args
    assert args[0] == "projects/p/topics/market-indices"
    body = args[1]
    assert b"VNINDEX" in body
    assert kwargs == {"symbol": "VNINDEX", "asset_class": "index"}
    mock_future.result.assert_called_once_with(timeout=10)


@pytest.mark.unit
@patch("publisher.pubsub_publisher.pubsub_v1.PublisherClient")
def test_publish_raises_on_publish_failure(mock_client_cls, sample_index):
    mock_client = MagicMock()
    mock_client.topic_path.return_value = "projects/p/topics/market-indices"
    mock_future = MagicMock()
    mock_future.result.side_effect = TimeoutError("publish timeout")
    mock_client.publish.return_value = mock_future
    mock_client_cls.return_value = mock_client

    p = PubsubPublisher("p", "market-indices")
    with pytest.raises(TimeoutError):
        p.publish(sample_index, attributes={})


@pytest.mark.unit
@patch("publisher.pubsub_publisher.pubsub_v1.PublisherClient")
def test_flush_is_noop(mock_client_cls):
    p = PubsubPublisher("p", "topic-x")
    p.flush()  # no exception, does nothing observable
