import base64
import json

import pytest

from cu_commons.apis import github
from cu_commons.errors import ApiError, AuthError


def b64(text):
    return base64.b64encode(text.encode()).decode()


class FakeGitHub:
    """In-memory contents API: GET returns the file, PUT checks the sha like GitHub does."""

    def __init__(self, files=None, conflicts=0):
        self.files = {p: (t, f"sha{i}") for i, (p, t) in enumerate((files or {}).items())}
        self.conflicts, self.puts, self.n = conflicts, [], 100

    def __call__(self, method, url, **kw):
        path = url.split("/contents/", 1)[1]
        assert kw["headers"]["Authorization"] == "Bearer T"
        if method == "GET":
            if path not in self.files:
                raise ApiError("not found", 404)
            text, sha = self.files[path]
            return {"type": "file", "encoding": "base64", "content": b64(text), "sha": sha}
        body = kw["json"]
        current = self.files.get(path, (None, None))[1]
        if self.conflicts:
            self.conflicts -= 1
            self.n += 1
            self.files[path] = (self.files[path][0] + "X", f"sha{self.n}")  # someone else pushed
            raise ApiError("sha mismatch", 409)
        if body.get("sha") != current:
            raise ApiError("sha mismatch", 409)
        self.n += 1
        self.files[path] = (base64.b64decode(body["content"]).decode(), f"sha{self.n}")
        self.puts.append(body)
        return {"commit": {"sha": f"c{self.n}"}}


@pytest.fixture
def repo(monkeypatch):
    def make(files=None, conflicts=0):
        fake = FakeGitHub(files, conflicts)
        monkeypatch.setattr(github, "request_json", fake)
        return github.GitHubRepo("T", "me/repo", branch="dev"), fake
    return make


def test_get_file_and_missing(repo):
    r, _ = repo({"a.json": '{"x": 1}'})
    f = r.get_file("a.json")
    assert (f.text, f.sha) == ('{"x": 1}', "sha0")
    assert r.get_file("nope.json") is None
    assert r.get_json("nope.json", default={}) == {}


def test_put_file_sends_branch_and_base64(repo):
    r, fake = repo({"a.txt": "old"})
    assert r.put_file("a.txt", "new ₹", "msg", sha="sha0").startswith("c")
    assert fake.puts[0]["branch"] == "dev" and base64.b64decode(fake.puts[0]["content"]).decode() == "new ₹"


def test_update_text_retries_on_concurrent_edit(repo):
    r, fake = repo({"log.txt": "a\n"}, conflicts=1)
    r.update_text("log.txt", lambda t: t + "b\n", "append")
    assert fake.files["log.txt"][0] == "a\nXb\n"  # re-read after the conflict: the other edit is kept


def test_update_text_gives_up_after_attempts(repo):
    r, _ = repo({"log.txt": "a"}, conflicts=5)
    with pytest.raises(ApiError):
        r.update_text("log.txt", lambda t: t + "b", "append", attempts=2)


def test_update_text_no_change_makes_no_commit(repo):
    r, fake = repo({"a.txt": "same"})
    assert r.update_text("a.txt", lambda t: t, "noop") is None and fake.puts == []


def test_update_json_custom_dumps_and_create(repo):
    r, fake = repo({})
    r.update_json("l.json", lambda d: d.setdefault("entries", []).append({"amount": 92}), "add",
                  dumps=lambda o: json.dumps(o) + "\n", create=True)
    assert fake.files["l.json"][0] == '{"entries": [{"amount": 92}]}\n'
    assert "sha" not in fake.puts[0]  # created, not updated


def test_missing_file_without_create_raises(repo):
    r, _ = repo({})
    with pytest.raises(ApiError):
        r.update_text("x.txt", lambda t: "y", "m")


def test_auth_errors_are_explained(monkeypatch):
    def deny(*a, **k):
        raise ApiError("bad credentials", 401)
    monkeypatch.setattr(github, "request_json", deny)
    with pytest.raises(AuthError):
        github.GitHubRepo("T", "me/repo").get_file("a")


def test_constructor_validation():
    with pytest.raises(ValueError):
        github.GitHubRepo("", "me/repo")
    with pytest.raises(ValueError):
        github.GitHubRepo("T", "repo-without-owner")
