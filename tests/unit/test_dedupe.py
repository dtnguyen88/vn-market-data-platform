"""Unit tests for alerter.dedupe — uses MagicMock Firestore."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from alerter.dedupe import AlertDeduper, _sanitize_key, _ttl_for


def _mk_client(exists: bool, expires_at: datetime | None = None):
    snap = MagicMock()
    snap.exists = exists
    snap.to_dict.return_value = {"expires_at": expires_at} if exists else None

    doc_ref = MagicMock()
    doc_ref.get.return_value = snap
    doc_ref.set = MagicMock()

    coll = MagicMock()
    coll.document.return_value = doc_ref

    client = MagicMock()
    client.collection.return_value = coll
    return client, doc_ref


@pytest.mark.unit
def test_critical_always_sends():
    client, doc_ref = _mk_client(exists=True, expires_at=datetime.now(UTC) + timedelta(hours=1))
    d = AlertDeduper(client)
    assert d.should_send("any-key", "critical") is True
    # No Firestore write for critical (bypass)
    doc_ref.set.assert_not_called()


@pytest.mark.unit
def test_first_send_new_key_writes_doc():
    client, doc_ref = _mk_client(exists=False)
    d = AlertDeduper(client)
    assert d.should_send("alert-A", "warning") is True
    doc_ref.set.assert_called_once()
    written = doc_ref.set.call_args.args[0]
    assert written["severity"] == "warning"


@pytest.mark.unit
def test_within_window_dedupes():
    future = datetime.now(UTC) + timedelta(minutes=5)
    client, doc_ref = _mk_client(exists=True, expires_at=future)
    d = AlertDeduper(client)
    assert d.should_send("alert-A", "warning") is False
    doc_ref.set.assert_not_called()


@pytest.mark.unit
def test_after_window_resends():
    past = datetime.now(UTC) - timedelta(minutes=1)
    client, doc_ref = _mk_client(exists=True, expires_at=past)
    d = AlertDeduper(client)
    assert d.should_send("alert-A", "warning") is True
    doc_ref.set.assert_called_once()


@pytest.mark.unit
def test_ttl_for_severity():
    assert _ttl_for("info") == 3600
    assert _ttl_for("warning") == 600
    assert _ttl_for("debug") == 300
    assert _ttl_for("critical") == 0
    assert _ttl_for("error") == 600
    assert _ttl_for("unknown-sev") == 600  # default


@pytest.mark.unit
def test_sanitize_key_replaces_slashes():
    assert _sanitize_key("a/b/c") == "a_b_c"


@pytest.mark.unit
def test_sanitize_key_truncates():
    long = "x" * 2000
    assert len(_sanitize_key(long)) == 1500
