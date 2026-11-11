"""Strava API v3 client with automatic access-token refresh.

Strava rotates refresh tokens: pass ``on_refresh`` to persist the new one (e.g. to SSM via
``cu_commons.config.put_ssm``, or to a file). Get the first refresh token once via the OAuth flow
(scope ``read,activity:read_all``).
"""
import os
import time

from cu_commons.errors import ApiError, AuthError, NoDataError
from cu_commons.http import request_json

API = "https://www.strava.com/api/v3"
TOKEN_URL = "https://www.strava.com/oauth/token"


class StravaClient:
    def __init__(self, client_id: str, client_secret: str, refresh_token: str, on_refresh=None,
                 access_token: str | None = None, expires_at: int = 0):
        if not (client_id and client_secret and refresh_token):
            raise ValueError("Strava client_id, client_secret and refresh_token are required")
        self.client_id, self.client_secret, self.refresh_token = client_id, client_secret, refresh_token
        self.on_refresh, self.access_token, self.expires_at = on_refresh, access_token, expires_at

    @classmethod
    def from_env(cls, on_refresh=None, id_var="StravaClientId", secret_var="StravaClientSecret",
                 refresh_var="StravaRefreshToken"):
        return cls(os.environ.get(id_var, ""), os.environ.get(secret_var, ""), os.environ.get(refresh_var, ""),
                   on_refresh=on_refresh)

    def _token(self) -> str:
        if self.access_token and self.expires_at - 60 > time.time():
            return self.access_token
        try:
            body = request_json("POST", TOKEN_URL, data={"client_id": self.client_id, "client_secret": self.client_secret,
                                                         "grant_type": "refresh_token", "refresh_token": self.refresh_token})
        except ApiError as e:
            if e.status_code in (400, 401):
                raise AuthError("Strava refused the refresh token; redo the OAuth step") from e
            raise
        self.access_token, self.expires_at = body["access_token"], int(body["expires_at"])
        new_refresh = body.get("refresh_token")
        if new_refresh and new_refresh != self.refresh_token:
            self.refresh_token = new_refresh
            if self.on_refresh:
                self.on_refresh(new_refresh)
        return self.access_token

    def get(self, path: str, **params):
        try:
            return request_json("GET", f"{API}{path}", params=params,
                                headers={"Authorization": f"Bearer {self._token()}"})
        except ApiError as e:
            if e.status_code == 401:
                raise AuthError("Strava access was revoked or lacks the activity:read_all scope") from e
            raise

    def athlete(self) -> dict:
        return self.get("/athlete")

    def activities(self, after: int | None = None, before: int | None = None, page: int = 1, per_page: int = 30) -> list:
        params = {"page": page, "per_page": per_page}
        if after:
            params["after"] = after
        if before:
            params["before"] = before
        return self.get("/athlete/activities", **params)

    def activity(self, activity_id: int) -> dict:
        return self.get(f"/activities/{activity_id}")

    def latest(self, sport_type: str = "Run", lookback: int = 30) -> dict:
        for item in self.activities(per_page=lookback):
            if item.get("sport_type") == sport_type or item.get("type") == sport_type:
                return self.activity(item["id"])
        raise NoDataError(f"No {sport_type} in the last {lookback} activities")
