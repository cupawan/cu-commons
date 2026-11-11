import pytest

from cu_commons import http, telegram
from cu_commons.errors import ApiError


class Resp:
    def __init__(self, status, body=None, headers=None):
        self.status_code, self._body, self.headers = status, body, headers or {}
        self.content = b"x" if body is not None else b""
        self.text = str(body)

    def json(self):
        return self._body


class Session:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), 0

    def request(self, method, url, **kw):
        self.calls += 1
        return self.responses.pop(0)


def test_retries_rate_limit_then_succeeds(monkeypatch):
    waits = []
    monkeypatch.setattr(http.time, "sleep", waits.append)
    s = Session([Resp(429, {}, {"Retry-After": "2"}), Resp(503, {}), Resp(200, {"ok": True})])
    assert http.request_json("GET", "https://x", session=s) == {"ok": True}
    assert s.calls == 3 and waits[0] == 2.0


def test_client_errors_are_not_retried():
    s = Session([Resp(404, {"error": "nope"})])
    with pytest.raises(ApiError) as e:
        http.request_json("GET", "https://x", session=s)
    assert e.value.status_code == 404 and s.calls == 1


def test_send_message_payload(monkeypatch):
    sent = {}
    monkeypatch.setattr(telegram, "request_json", lambda m, url, **kw: sent.update(url=url, **kw) or {"ok": True, "result": 1})
    bot = telegram.TelegramBot("T")
    assert bot.send_message(42, "hi", reply_markup=bot.reply_keyboard([["📊 Recovery"]])) == 1
    assert sent["url"].endswith("/botT/sendMessage")
    assert sent["json"]["chat_id"] == 42 and "parse_mode" not in sent["json"]
    assert sent["json"]["reply_markup"]["keyboard"][0][0]["text"] == "📊 Recovery"


def test_edit_ignores_not_modified(monkeypatch):
    def boom(*a, **k):
        raise ApiError("Telegram editMessageText failed: message is not modified")
    monkeypatch.setattr(telegram, "request_json", boom)
    assert telegram.TelegramBot("T").edit_message(1, 2, "same") is None


def test_inline_keyboard_validates_callback_size():
    kb = telegram.TelegramBot.inline_keyboard([[("😀", "feel:3:2026-11-12")]])
    assert kb["inline_keyboard"][0][0]["callback_data"] == "feel:3:2026-11-12"
    with pytest.raises(ValueError):
        telegram.TelegramBot.inline_keyboard([[("x", "y" * 65)]])


def test_parse_update():
    cb = telegram.parse_update({"callback_query": {"id": "c", "data": "trend:x", "from": {"id": 7},
                                                   "message": {"message_id": 3, "chat": {"id": 9}}}})
    assert (cb["kind"], cb["user_id"], cb["chat_id"], cb["message_id"], cb["data"]) == ("callback", 7, 9, 3, "trend:x")
    msg = telegram.parse_update('{"message": {"from": {"id": 7}, "chat": {"id": 7}, "text": "/start"}}')
    assert (msg["kind"], msg["text"]) == ("text", "/start")
