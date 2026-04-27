"""Unit tests for publisher.config — env var parsing."""

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
    assert cfg.ssi_username_secret == "ssi-fc-username"  # default  # pragma: allowlist secret
    assert cfg.ssi_password_secret == "ssi-fc-password"  # default  # pragma: allowlist secret
    assert cfg.symbols_url.startswith("gs://")


@pytest.mark.unit
def test_from_env_secret_overrides(monkeypatch):
    monkeypatch.setenv("GCP_PROJECT_ID", "p")
    monkeypatch.setenv("SHARD", "0")
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("SYMBOLS_URL", "gs://b/s.json")
    monkeypatch.setenv("SSI_USERNAME_SECRET", "custom-user")  # pragma: allowlist secret
    monkeypatch.setenv("SSI_PASSWORD_SECRET", "custom-pwd")  # pragma: allowlist secret
    cfg = Config.from_env()
    assert cfg.ssi_username_secret == "custom-user"  # pragma: allowlist secret
    assert cfg.ssi_password_secret == "custom-pwd"  # pragma: allowlist secret


@pytest.mark.unit
def test_from_env_missing_required_raises(monkeypatch):
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
    monkeypatch.delenv("SHARD", raising=False)
    with pytest.raises(KeyError):
        Config.from_env()
