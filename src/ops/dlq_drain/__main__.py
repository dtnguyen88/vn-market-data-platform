"""DLQ drain Cloud Run Job. For each known DLQ, pull all messages, write to
GCS export, ack/delete. Alert via shared.alerts if any messages found.
"""

import json
import os
import time

from shared.alerts import publish_alert

DLQ_TOPICS = [
    "market-ticks-dlq",
    "market-quotes-l1-dlq",
    "market-quotes-l2-dlq",
    "market-indices-dlq",
    "platform-alerts-dlq",
]


def drain_one(project_id: str, env: str, topic_short_name: str) -> int:
    """Pull up to 1000 messages from a DLQ subscription, export to GCS, ack."""
    from google.cloud import pubsub_v1, storage

    bucket_name = f"vn-market-lake-{env}"
    sub_id = f"{topic_short_name}-drain-sub"
    subscriber = pubsub_v1.SubscriberClient()
    subscription_path = subscriber.subscription_path(project_id, sub_id)
    # Best-effort: assume subscription exists (operator pre-creates) or skip
    try:
        response = subscriber.pull(
            request={"subscription": subscription_path, "max_messages": 1000},
            timeout=10.0,
        )
    except Exception as e:
        print(f"DLQ pull failed for {topic_short_name}: {e}")
        return 0

    msgs = response.received_messages
    if not msgs:
        return 0

    storage_client = storage.Client(project=project_id)
    bucket = storage_client.bucket(bucket_name)
    ts = int(time.time() * 1000)
    blob_name = f"_ops/dlq-export/{topic_short_name}/run={ts}.jsonl"
    payload = "\n".join(
        json.dumps(
            {
                "data": m.message.data.decode("utf-8", errors="replace"),
                "attributes": dict(m.message.attributes or {}),
                "publish_time": (
                    m.message.publish_time.isoformat() if m.message.publish_time else None
                ),
            }
        )
        for m in msgs
    )
    bucket.blob(blob_name).upload_from_string(payload, content_type="application/x-ndjson")
    ack_ids = [m.ack_id for m in msgs]
    subscriber.acknowledge(request={"subscription": subscription_path, "ack_ids": ack_ids})
    return len(msgs)


def main() -> None:
    project_id = os.environ["GCP_PROJECT_ID"]
    env = os.environ.get("ENV", "staging")
    counts = {t: drain_one(project_id, env, t) for t in DLQ_TOPICS}
    total = sum(counts.values())
    summary = {"env": env, "counts": counts, "total": total}
    print(json.dumps(summary))
    if total > 0:
        try:
            publish_alert(
                project_id=project_id,
                severity="warning",
                name="dlq_drain_nonzero",
                body=(
                    f"DLQ drain found {total} messages across "
                    f"{sum(1 for v in counts.values() if v)} topics"
                ),
                extra=counts,
                source="dlq-drain",
            )
        except Exception as e:
            print(f"alert failed: {e}")


if __name__ == "__main__":
    main()
