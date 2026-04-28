"""Weekly data-quality validators. 4 SQL queries; row count > 0 = finding."""

import json
import os
from pathlib import Path

from shared.alerts import publish_alert

VALIDATORS = ["tick_vs_daily", "l1_vs_l2", "index_recompute", "corp_actions_applied"]


def main() -> None:
    project_id = os.environ["GCP_PROJECT_ID"]
    env = os.environ.get("ENV", "staging")
    here = Path(__file__).parent
    findings: dict[str, int] = {}

    from google.cloud import bigquery

    client = bigquery.Client(project=project_id)
    for v in VALIDATORS:
        sql_path = here / "validators" / f"{v}.sql"
        if not sql_path.exists():
            findings[v] = -1
            continue
        sql = sql_path.read_text().replace("{{ project_id }}", project_id).replace("{{ env }}", env)
        try:
            rows = list(client.query(sql).result())
            findings[v] = len(rows)
        except Exception as e:
            print(f"validator {v} failed: {e}")
            findings[v] = -1

    total = sum(c for c in findings.values() if c > 0)
    summary = {"env": env, "findings": findings, "total_findings": total}
    print(json.dumps(summary))

    if total > 0:
        try:
            publish_alert(
                project_id=project_id,
                severity="warning",
                name="data_quality_findings",
                body=(
                    f"weekly DQ run found {total} issues across "
                    f"{sum(1 for v in findings.values() if v > 0)} validators"
                ),
                source="data-quality",
                extra=findings,
            )
        except Exception as e:
            print(f"alert failed: {e}")


if __name__ == "__main__":
    main()
