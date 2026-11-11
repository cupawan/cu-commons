import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for key in ("SSM_PREFIX", "AlertsBotToken", "SelfTgChatId", "APP_ENV"):
        monkeypatch.delenv(key, raising=False)
    import cu_commons.config as config

    config._loaded_prefixes.clear()
    yield
