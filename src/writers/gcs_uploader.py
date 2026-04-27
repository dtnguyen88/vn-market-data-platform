"""Thin google-cloud-storage wrapper — upload bytes to GCS with deterministic key naming."""

from google.cloud import storage


class GcsUploader:
    """Wraps storage.Client to upload raw bytes to a fixed GCS bucket."""

    def __init__(self, bucket: str):
        self._client = storage.Client()
        self._bucket = self._client.bucket(bucket)

    def upload(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload data to gs://<bucket>/<key> and return the full GCS URI."""
        blob = self._bucket.blob(key)
        blob.upload_from_string(data, content_type=content_type)
        return f"gs://{self._bucket.name}/{key}"
