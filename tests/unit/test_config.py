"""Unit tests for publisher.config — env var parsing (SSI v3 secret names)."""

import pytest

from publisher.config import Config


@pytest.mark.unit
def test_from_env_required_fields(monkeypatch):
    monkeypatch.setenv("GCP_PROJECT_ID", "p")
    monkeypatch.setenv("SHARD", "2")
    monkeypatch.setenv("ENV", "staging")
    monkeypatch.setenv(
        "SYMBOLS_URL", "gs://vn-market-lake-staging/_ops/reference/symbols-shard-2.json"
    )
    cfg = Config.from_env()
    assert cfg.project_id == "p"
    assert cfg.shard == 2
    assert cfg.env == "staging"
    assert cfg.ssi_api_key_secret == "ssi-fc-api-key"  # default  # pragma: allowlist secret
    assert cfg.ssi_api_secret_secret == "ssi-fc-api-secret"  # default  # pragma: allowlist secret
    assert cfg.ssi_private_key_secret == "ssi-fc-rsa-private-key"  # pragma: allowlist secret
    assert cfg.symbols_url.startswith("gs://")


@pytest.mark.unit
def test_from_env_secret_overrides(monkeypatch):
    monkeypatch.setenv("GCP_PROJECT_ID", "p")
    monkeypatch.setenv("SHARD", "0")
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("SYMBOLS_URL", "gs://b/s.json")
    monkeypatch.setenv("SSI_API_KEY_SECRET", "custom-key")  # pragma: allowlist secret
    monkeypatch.setenv("SSI_API_SECRET_SECRET", "custom-secret")  # pragma: allowlist secret
    monkeypatch.setenv("SSI_PRIVATE_KEY_SECRET", "custom-pk")  # pragma: allowlist secret
    cfg = Config.from_env()
    assert cfg.ssi_api_key_secret == "custom-key"  # pragma: allowlist secret
    assert cfg.ssi_api_secret_secret == "custom-secret"  # pragma: allowlist secret
    assert cfg.ssi_private_key_secret == "custom-pk"  # pragma: allowlist secret


@pytest.mark.unit
def test_from_env_missing_required_raises(monkeypatch):
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
    monkeypatch.delenv("SHARD", raising=False)
    with pytest.raises(KeyError):
        Config.from_env()
