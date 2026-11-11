import os
from datetime import date

import pytest

from cu_commons import config, dates
from cu_commons.errors import ConfigError
from cu_commons.utils import dig, find_key, to_int


def test_dates():
    assert dates.hm(7260) == "2h 01m" and dates.hm(None) == "-"
    assert dates.pace(1000 / 300) == "5'00\"/km" and dates.pace(0) == "-"
    assert dates.from_timestamp(1762835400).date() == dates.from_timestamp(1762835400000).date()
    assert isinstance(dates.today(), date)


def test_utils():
    data = {"a": [{"b": None}, {"c": {"b": 5}}]}
    assert find_key(data, "b") == 5 and find_key(data, "zz") is None
    assert dig({"x": [{"y": 1}]}, "x", "y") == 1 and dig({}, "x", default=0) == 0
    assert to_int("4.6") == 5 and to_int(None) is None and to_int("n/a") is None


def test_config_get(monkeypatch):
    monkeypatch.setenv("FOO", "1")
    assert config.get("FOO") == "1"
    assert config.get("MISSING_X", required=False) is None
    with pytest.raises(ConfigError):
        config.get("MISSING_X")


class FakeSSM:
    def __init__(self):
        self.puts = []

    def get_paginator(self, _):
        class P:
            def paginate(self, **kw):
                assert kw["Path"] == "/app/dev/" and kw["WithDecryption"]
                yield {"Parameters": [{"Name": "/app/dev/TokenA", "Value": "ssm"}, {"Name": "/app/dev/Keep", "Value": "ssm"}]}
        return P()

    def put_parameter(self, **kw):
        self.puts.append(kw)


def test_load_ssm_env_wins_and_caches(monkeypatch):
    monkeypatch.delenv("TokenA", raising=False)
    monkeypatch.setenv("Keep", "env")
    ssm = FakeSSM()
    assert config.load_ssm("/app/dev", client=ssm) == 1
    assert os.environ["TokenA"] == "ssm" and os.environ["Keep"] == "env"
    assert config.load_ssm("/app/dev", client=ssm) == 0
    monkeypatch.delenv("TokenA", raising=False)


def test_put_ssm(monkeypatch):
    ssm = FakeSSM()
    config.put_ssm("Rotated", "v2", "/app/dev", client=ssm)
    assert ssm.puts[0]["Name"] == "/app/dev/Rotated" and ssm.puts[0]["Type"] == "SecureString"
    assert os.environ["Rotated"] == "v2"
    monkeypatch.delenv("Rotated", raising=False)
