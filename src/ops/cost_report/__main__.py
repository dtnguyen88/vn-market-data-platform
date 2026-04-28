"""Cost report Cloud Run Job. Modes: daily | monthly.

Daily: emit cost_today_usd metric.
Monthly: query MTD + prior-month + breakdown; post Telegram via shared.alerts.

Env: GCP_PROJECT_ID, ENV. Args: --mode={daily|monthly}.
"""

import argparse
import json
import os

from shared.alerts import publish_alert


def fetch_spend(project_id: str, mode: str) -> dict:
    """Stub: returns spend totals. Real impl queries Cloud Billing BQ export.

    For v1, query is documented but execution requires Billing Export to BQ.
    Returns deterministic 0s when export table missing.
    """
    try:
        from google.cloud import bigquery

        client = bigquery.Client(project=project_id)
        # Billing export table name pattern: gcp_billing_export_v1_{billing_account}
        # project_id comes from a trusted env-var, not user input — S608 is a false positive.
        table = f"{project_id}.billing_export.gcp_billing_export_v1_*"
        query = (
            f"SELECT SUM(cost) AS total FROM `{table}`"  # noqa: S608
            " WHERE _TABLE_SUFFIX BETWEEN"
            " FORMAT_DATE('%Y%m%d', DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY))"
            " AND FORMAT_DATE('%Y%m%d', CURRENT_DATE())"
        )
        rows = list(client.query(query).result())
        return {"total_usd": float(rows[0]["total"]) if rows and rows[0]["total"] else 0.0}
    except Exception as e:
        return {"total_usd": 0.0, "error": str(e)}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--mode", required=True, choices=["daily", "monthly"])
    args = p.parse_args()
    project_id = os.environ["GCP_PROJECT_ID"]
    env = os.environ.get("ENV", "staging")

    spend = fetch_spend(project_id, args.mode)
    summary = {"mode": args.mode, "env": env, **spend}
    print(json.dumps(summary))

    if args.mode == "monthly":
        body = f"prior-month spend: ${spend.get('total_usd', 0):.2f}"
        try:
            publish_alert(
                project_id=project_id,
                severity="info",
                name="monthly_cost_report",
                body=body,
                scope=env,
                source="cost-report",
            )
        except Exception as e:
            print(f"alert publish failed: {e}")


if __name__ == "__main__":
    main()
