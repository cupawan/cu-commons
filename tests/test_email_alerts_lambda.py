from cu_commons.alerts import TelegramAlerter
from cu_commons.aws import event_kind, lambda_handler
from cu_commons.email import SmtpEmail
from cu_commons.errors import NoDataError


def test_email_build_html_with_attachment():
    msg = SmtpEmail("me@x.com", "pw", sender_name="Bot").build(["a@x.com", "b@x.com"], "Hi", "<b>hi</b>", html=True,
                                                                attachments=[("r.csv", b"a,b\n1,2")])
    assert msg["From"] == "Bot <me@x.com>" and msg["To"] == "a@x.com, b@x.com"
    assert [p.get_filename() for p in msg.iter_attachments()] == ["r.csv"]


def test_alerter_optional_without_env():
    assert TelegramAlerter.from_env() is None


class FakeAlerter:
    def __init__(self):
        self.notes, self.errors = [], []

    def notify(self, text):
        self.notes.append(text)

    def error(self, service, exc, extra=None):
        self.errors.append((service, str(exc), extra))


def test_lambda_handler_paths(monkeypatch):
    alert = FakeAlerter()

    @lambda_handler("svc", alerter=alert)
    def ok(event, context):
        return None

    @lambda_handler("svc", alerter=alert)
    def empty(event, context):
        raise NoDataError("no run today")

    @lambda_handler("svc", alerter=alert)
    def boom(event, context):
        raise RuntimeError("bad")

    assert ok({}, None) == {"statusCode": 200, "body": "OK"}
    assert empty({}, None)["statusCode"] == 200 and alert.notes == ["[svc] no run today"]
    assert boom({"source": "schedule"}, None)["statusCode"] == 500
    assert alert.errors == [("svc", "bad", {"event_kind": "schedule"})]


def test_lambda_handler_loads_ssm(monkeypatch):
    seen = []
    monkeypatch.setattr("cu_commons.config.load_ssm", seen.append)
    monkeypatch.setenv("SSM_PREFIX", "/app/prod/")

    @lambda_handler("svc", alerter=FakeAlerter())
    def fn(event, context):
        return {"statusCode": 200}

    fn({}, None)
    assert seen == ["/app/prod/"]


def test_event_kind():
    assert event_kind({"source": "schedule"}) == "schedule" and event_kind({"body": "{}"}) == "http"
    assert event_kind({}) == "unknown"
