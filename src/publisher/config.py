"""Publisher config. All env vars.

Secret names changed for SSI FastConnect v3 (2026-05-26):
  v2 names (deprecated): ssi-fc-username, ssi-fc-password
  v3 names (current):    ssi-fc-api-key, ssi-fc-api-secret, ssi-fc-rsa-private-key
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    project_id: str
    shard: int
    env: str
    ssi_api_key_secret: str
    ssi_api_secret_secret: str
    ssi_private_key_secret: str
    symbols_url: str  # e.g. gs://vn-market-lake-{env}/_ops/reference/symbols-shard-{N}.json

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            project_id=os.environ["GCP_PROJECT_ID"],
            shard=int(os.environ["SHARD"]),
            env=os.environ["ENV"],
            ssi_api_key_secret=os.environ.get("SSI_API_KEY_SECRET", "ssi-fc-api-key"),
            ssi_api_secret_secret=os.environ.get("SSI_API_SECRET_SECRET", "ssi-fc-api-secret"),
            ssi_private_key_secret=os.environ.get(
                "SSI_PRIVATE_KEY_SECRET", "ssi-fc-rsa-private-key"
            ),
            symbols_url=os.environ["SYMBOLS_URL"],
        )
