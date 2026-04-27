"""Heartbeat custom metric for Cloud Monitoring liveness alert."""

import asyncio
import time

from google.cloud import monitoring_v3


class Heartbeat:
    def __init__(self, project_id: str, shard: int):
        self.client = monitoring_v3.MetricServiceClient()
        self.project_name = f"projects/{project_id}"
        self.shard = shard

    async def run(self, interval_s: int = 30):
        while True:
            self._emit()
            await asyncio.sleep(interval_s)

    def _emit(self):
        series = monitoring_v3.TimeSeries()
        series.metric.type = "custom.googleapis.com/publisher/heartbeat"
        series.metric.labels["shard"] = str(self.shard)
        series.resource.type = "global"
        point = monitoring_v3.Point()
        point.value.double_value = 1.0
        point.interval.end_time.seconds = int(time.time())
        series.points = [point]
        self.client.create_time_series(name=self.project_name, time_series=[series])
