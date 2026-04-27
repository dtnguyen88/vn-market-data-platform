"""Pub/Sub publishing helper. One PubsubPublisher per topic.

Publishes JSON-serialized message body with structured attributes for downstream filtering.
"""

import logging

from google.cloud import pubsub_v1
from pydantic import BaseModel

log = logging.getLogger(__name__)


class PubsubPublisher:
    def __init__(self, project_id: str, topic: str):
        self.client = pubsub_v1.PublisherClient()
        self.topic_path = self.client.topic_path(project_id, topic)

    def publish(self, msg: BaseModel, attributes: dict[str, str]) -> None:
        body = msg.model_dump_json().encode("utf-8")
        future = self.client.publish(self.topic_path, body, **attributes)
        # block briefly to surface errors; for higher throughput, batch via flush()
        future.result(timeout=10)

    def flush(self) -> None:
        # google client batches automatically; called on shutdown
        pass
