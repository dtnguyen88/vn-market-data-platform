"""Helper for any Python service to publish alerts to platform-alerts topic.

Workflows publish directly via the Pub/Sub call step. Python services
(publisher, writers, batch jobs) use this helper.

Usage:
    from shared.alerts import publish_alert
    publish_alert(
        project_id="vn-market-platform-staging",
        severity="critical",
        name="ssi_auth_failed",
        body="SSI WS auth rejected; check secret rotation",
        scope="publisher-shard-0",
    )
"""

import json
from typing import Any

from google.cloud import pubsub_v1


def publish_alert(
    project_id: str,
    severity: str,
    name: str,
    body: str,
    scope: str = "",
    source: str | None = None,
    extra: dict[str, Any] | None = None,
    topic: str = "platform-alerts",
) -> str:
    """Publish a structured alert payload. Returns the Pub/Sub message ID."""
    client = pubsub_v1.PublisherClient()
    topic_path = client.topic_path(project_id, topic)
    payload = {
        "severity": severity,
        "name": name,
        "body": body,
        "scope": scope,
        "source": source,
        "extra": extra or {},
    }
    attrs = {"severity": severity, "alert_name": name}
    if scope:
        attrs["scope"] = scope
    if source:
        attrs["source"] = source
    future = client.publish(topic_path, json.dumps(payload).encode("utf-8"), **attrs)
    return future.result(timeout=10)
