"""Smoke test for ops.cost_report.fetch_spend (handles missing BQ export gracefully)."""

from unittest.mock import MagicMock, patch

import pytest
from ops.cost_report.__main__ import fetch_spend


@pytest.mark.unit
def test_fetch_spend_returns_dict_with_total_on_error():
    # When BQ Client raises (e.g., billing export not configured), function returns 0.0.
    # bigquery is imported lazily inside fetch_spend, so patch at the module level.
    mock_bq = MagicMock()
    mock_bq.Client.side_effect = RuntimeError("no billing export")
    with patch.dict("sys.modules", {"google.cloud.bigquery": mock_bq}):
        result = fetch_spend("p", "daily")
    assert result["total_usd"] == 0.0
    assert "error" in result
