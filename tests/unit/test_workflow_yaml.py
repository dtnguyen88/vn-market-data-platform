"""Unit tests verifying all workflow YAMLs parse cleanly + have expected structure."""

from pathlib import Path

import pytest
import yaml

WF_DIR = Path(__file__).parent.parent.parent / "infra" / "workflows"

EXPECTED_WORKFLOWS = {
    "shared-check-trading-day.yaml",
    "eod-pipeline.yaml",
    "intraday-coverage-check.yaml",
    "reference-refresh.yaml",
    "curate-fallback.yaml",
    "calendar-refresh-yearly.yaml",
    "monthly-cost-report.yaml",
}


@pytest.mark.unit
def test_all_expected_workflows_present():
    actual = {p.name for p in WF_DIR.glob("*.yaml")}
    assert actual == EXPECTED_WORKFLOWS


@pytest.mark.unit
@pytest.mark.parametrize("yaml_name", sorted(EXPECTED_WORKFLOWS))
def test_workflow_parses_and_has_main(yaml_name):
    path = WF_DIR / yaml_name
    doc = yaml.safe_load(path.read_text())
    assert "main" in doc, f"{yaml_name}: missing top-level 'main' key"
    assert "steps" in doc["main"], f"{yaml_name}: main.steps missing"
    steps = doc["main"]["steps"]
    assert isinstance(steps, list) and len(steps) > 0, f"{yaml_name}: steps empty"
