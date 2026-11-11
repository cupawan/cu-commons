import pytest

from cu_commons.db.mongo import Mongo
from cu_commons.db.postgres import Postgres, normalize_url


def test_neon_url():
    url, tls = normalize_url("postgresql://u:p@ep-x-pooler.aws.neon.tech/automations?sslmode=require&channel_binding=require")
    assert url == "postgresql+pg8000://u:p@ep-x-pooler.aws.neon.tech/automations" and tls


def test_local_url_without_tls():
    assert normalize_url("postgres://u:p@localhost:5432/db?sslmode=disable") == ("postgresql+pg8000://u:p@localhost:5432/db", False)


def test_required_settings(monkeypatch):
    with pytest.raises(ValueError):
        Postgres("")
    monkeypatch.delenv("MONGO_DATABASE", raising=False)
    monkeypatch.setenv("MongoUrl", "mongodb://x")
    with pytest.raises(ValueError):
        Mongo.from_env()
    assert Mongo("mongodb://x", "automations_dev").database_name == "automations_dev"
