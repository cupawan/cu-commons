import io
import json

import pytest

from cu_commons import telegram
from cu_commons.apis import sheets, strava
from cu_commons.aws import s3
from cu_commons.errors import ApiError


class Resp:
    def __init__(self, status=200, body=None, content=b""):
        self.status_code, self._body = status, body
        self.content = content or (json.dumps(body).encode() if body is not None else b"")

    def json(self):
        return self._body


def test_download_file(monkeypatch):
    monkeypatch.setattr(telegram, "request_json", lambda m, url, **kw: {"ok": True, "result": {"file_path": "docs/a.pdf"}})
    got = {}
    monkeypatch.setattr(telegram.requests, "get", lambda url, timeout: got.update(url=url) or Resp(content=b"PDF"))
    assert telegram.TelegramBot("T").download_file("F1") == b"PDF"
    assert got["url"] == "https://api.telegram.org/file/botT/docs/a.pdf"


def test_send_photo_and_errors(monkeypatch):
    sent = {}

    def post(url, data, files, timeout):
        sent.update(url=url, field=list(files)[0])
        return Resp(body={"ok": True, "result": {"message_id": 5}})

    monkeypatch.setattr(telegram.requests, "post", post)
    assert telegram.TelegramBot("T").send_photo(1, "chart.png", b"png")["message_id"] == 5
    assert sent["url"].endswith("/sendPhoto") and sent["field"] == "photo"
    monkeypatch.setattr(telegram.requests, "post", lambda *a, **k: Resp(400, {"ok": False}))
    with pytest.raises(ApiError):
        telegram.TelegramBot("T").send_document(1, "a.csv", b"x")


def test_parse_update_photo_and_caption():
    u = telegram.parse_update({"message": {"from": {"id": 1}, "chat": {"id": 1}, "caption": "receipt",
                                           "photo": [{"file_id": "small"}, {"file_id": "large"}]}})
    assert (u["kind"], u["photo_file_id"], u["text"]) == ("photo", "large", "receipt")


def test_strava_oauth_helpers(monkeypatch):
    url = strava.authorization_url("123")
    assert url.startswith(strava.AUTHORIZE_URL) and "client_id=123" in url and "activity%3Aread_all" in url
    seen = {}
    monkeypatch.setattr(strava, "request_json", lambda m, u, **kw: seen.update(kw["data"]) or {"refresh_token": "R"})
    assert strava.exchange_code("123", "s", "CODE")["refresh_token"] == "R"
    assert seen["grant_type"] == "authorization_code" and seen["code"] == "CODE"


class FakeS3:
    class exceptions:
        class NoSuchKey(Exception):
            pass

    def __init__(self):
        self.store = {}

    def put_object(self, Bucket, Key, Body, ContentType):
        self.store[(Bucket, Key)] = (Body, ContentType)

    def get_object(self, Bucket, Key):
        if (Bucket, Key) not in self.store:
            raise self.exceptions.NoSuchKey()
        return {"Body": io.BytesIO(self.store[(Bucket, Key)][0])}

    def generate_presigned_url(self, op, Params, ExpiresIn):
        return f"https://s3/{Params['Bucket']}/{Params['Key']}?exp={ExpiresIn}"


def test_s3_helpers():
    fake = FakeS3()
    s3.put_json("b", "k.json", {"a": 1}, client=fake)
    assert fake.store[("b", "k.json")][1] == "application/json"
    assert s3.get_json("b", "k.json", client=fake) == {"a": 1}
    assert s3.get_json("b", "missing", default={}, client=fake) == {}
    assert s3.share_link("b", "k.json", 60, client=fake).endswith("exp=60")


def test_sheet_with_fake_client():
    calls = []

    class WS:
        def get_all_records(self):
            return [{"name": "x"}]

        def append_rows(self, rows, value_input_option):
            calls.append(("append", rows, value_input_option))

    class Book:
        sheet1 = WS()

        def worksheet(self, name):
            return WS()

    class Client:
        def open_by_key(self, key):
            calls.append(("open", key))
            return Book()

    sheet = sheets.Sheet(credentials={}, spreadsheet_id="ID", client=Client())
    assert sheet.records() == [{"name": "x"}]
    sheet.append([[1, 2]])
    assert calls == [("open", "ID"), ("append", [[1, 2]], "USER_ENTERED")]
