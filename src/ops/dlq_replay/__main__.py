"""DLQ replay (manual). Reads exported JSONL from GCS, re-publishes to topic.

Args: --export-uri gs://...  --target-topic market-ticks
"""

import argparse
import json
import os


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--export-uri", required=True)
    p.add_argument("--target-topic", required=True)
    args = p.parse_args()
    project_id = os.environ["GCP_PROJECT_ID"]

    from google.cloud import pubsub_v1, storage

    storage_client = storage.Client(project=project_id)
    bucket_name = args.export_uri.replace("gs://", "").split("/", 1)[0]
    blob_name = args.export_uri.replace(f"gs://{bucket_name}/", "")
    text = storage_client.bucket(bucket_name).blob(blob_name).download_as_text()

    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(project_id, args.target_topic)
    n = 0
    for line in text.splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        data = rec["data"].encode("utf-8")
        attrs = rec.get("attributes", {})
        attrs["replay_of"] = args.export_uri  # marker to detect replay-of-replay
        publisher.publish(topic_path, data, **attrs).result(timeout=10)
        n += 1
    print(json.dumps({"replayed": n, "from": args.export_uri, "to": args.target_topic}))


if __name__ == "__main__":
    main()
