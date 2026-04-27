"""Publisher config. All env vars."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    project_id: str
    shard: int
    env: str
    ssi_username_secret: str
    ssi_password_secret: str
    symbols_url: str  # e.g. gs://vn-market-lake-{env}/_ops/reference/symbols-shard-{N}.json

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            project_id=os.environ["GCP_PROJECT_ID"],
            shard=int(os.environ["SHARD"]),
            env=os.environ["ENV"],
            ssi_username_secret=os.environ.get("SSI_USERNAME_SECRET", "ssi-fc-username"),
            ssi_password_secret=os.environ.get("SSI_PASSWORD_SECRET", "ssi-fc-password"),
            symbols_url=os.environ["SYMBOLS_URL"],
        )
