"""GitHub repository files via the REST API: read a file, commit a change, and edit safely under concurrency.

Built for small bots that keep their state as files in a repo (e.g. a JSON ledger edited from Telegram):
every write is a real commit, so the repo's own history, CI and review stay the source of truth.

Token: a fine-grained personal access token limited to the one repository, permission
"Contents: Read and write". Nothing else is needed.

Concurrency: GitHub rejects a write whose ``sha`` is no longer the file's current blob (HTTP 409/422).
``update_text`` / ``update_json`` re-read and re-apply your change when that happens, so a bot commit and a
push from your laptop can't silently overwrite each other.
"""
import base64
import json
import os
from dataclasses import dataclass

from cu_commons.errors import ApiError, AuthError
from cu_commons.http import request_json

API = "https://api.github.com"
CONFLICT = {409, 422}


@dataclass
class RepoFile:
    path: str
    text: str
    sha: str


class GitHubRepo:
    def __init__(self, token: str, repo: str, branch: str = "main", api: str = API, timeout: float = 30):
        if not token:
            raise ValueError("GitHub token is required")
        if repo.count("/") != 1:
            raise ValueError(f"repo must be 'owner/name', got {repo!r}")
        self.repo, self.branch, self.api, self.timeout = repo, branch, api.rstrip("/"), timeout
        self.headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28"}

    @classmethod
    def from_env(cls, token_var: str = "GitHubToken", repo_var: str = "GitHubRepo", branch_var: str = "GitHubBranch"):
        return cls(os.environ.get(token_var, ""), os.environ.get(repo_var, ""), os.environ.get(branch_var) or "main")

    def _url(self, path: str) -> str:
        return f"{self.api}/repos/{self.repo}/contents/{path.lstrip('/')}"

    def _call(self, method: str, path: str, **kw):
        try:
            return request_json(method, self._url(path), headers=self.headers, timeout=self.timeout, **kw)
        except ApiError as e:
            if e.status_code in (401, 403):
                raise AuthError(f"GitHub refused the token for {self.repo} ({e.status_code}); "
                                "check it is not expired and has Contents: read and write") from e
            raise

    # ---- read
    def get_file(self, path: str) -> RepoFile | None:
        """Current text and blob sha on the branch, or None if the file doesn't exist."""
        try:
            body = self._call("GET", path, params={"ref": self.branch})
        except ApiError as e:
            if e.status_code == 404:
                return None
            raise
        if isinstance(body, list) or body.get("type") != "file":
            raise ApiError(f"{path} is not a file")
        if body.get("encoding") != "base64" or body.get("content") is None:
            raise ApiError(f"{path}: content not returned inline (files over 1 MB are not supported)")
        return RepoFile(path, base64.b64decode(body["content"]).decode("utf-8"), body["sha"])

    def get_json(self, path: str, default=None):
        f = self.get_file(path)
        return default if f is None else json.loads(f.text)

    # ---- write
    def put_file(self, path: str, text: str, message: str, sha: str | None = None,
                 author: dict | None = None) -> str:
        """Create (sha=None) or update (sha = the sha you read) a file in one commit. Returns the commit sha."""
        payload = {"message": message, "content": base64.b64encode(text.encode("utf-8")).decode("ascii"),
                   "branch": self.branch}
        if sha:
            payload["sha"] = sha
        if author:
            payload["author"] = payload["committer"] = author  # {"name": ..., "email": ...}
        body = self._call("PUT", path, json=payload)
        return body["commit"]["sha"]

    def update_text(self, path: str, change, message: str, attempts: int = 3, create: bool = False,
                    author: dict | None = None) -> str | None:
        """Read -> change(text) -> commit, retrying on a concurrent edit.

        `change(text)` returns the new text, or None to make no commit. With create=True a missing file is
        passed to `change` as "". Returns the commit sha, or None when nothing changed.
        """
        for attempt in range(1, attempts + 1):
            current = self.get_file(path)
            if current is None and not create:
                raise ApiError(f"{path} does not exist on {self.branch}")
            old = current.text if current else ""
            new = change(old)
            if new is None or new == old:
                return None
            try:
                return self.put_file(path, new, message, sha=current.sha if current else None, author=author)
            except ApiError as e:
                if e.status_code in CONFLICT and attempt < attempts:
                    continue  # someone else committed in between: re-read and re-apply
                raise
        return None

    def update_json(self, path: str, change, message: str, dumps=None, **kw) -> str | None:
        """Like update_text for JSON. `change(data)` edits the object in place or returns a new one.

        `dumps(obj) -> str` controls formatting (default: indent=4 + newline). Pass your own to keep a
        hand-formatted file's layout, so commits show only the lines that changed.
        """
        dumps = dumps or (lambda obj: json.dumps(obj, indent=4, ensure_ascii=False) + "\n")

        def _change(text):
            data = json.loads(text) if text.strip() else {}
            result = change(data)
            return dumps(data if result is None else result)

        return self.update_text(path, _change, message, **kw)
