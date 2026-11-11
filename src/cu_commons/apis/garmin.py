"""Garmin Connect Personal API (official, read-only), via Garmin's own `garmin-connect-personal-api-python`.

Create a key at https://connect.garmin.com/app/settings/personalApiToken (valid 30 days to 1 year).
The key is exchanged for a 24-hour bearer token, cached on disk (default /tmp, Lambda-friendly).
Not available in this API: Training Readiness / Status, VO2 max trends, devices, workouts.

Raw methods return Garmin's JSON; ``sleep_metrics`` / ``hrv_metrics`` / ``daily_metrics`` turn it into
small dataclasses with the fields most automations need.
"""
import logging
import os
import time
from dataclasses import dataclass
from datetime import date

from cu_commons.errors import ApiError, AuthError
from cu_commons.utils import dig, find_key, to_int

logger = logging.getLogger(__name__)
KEY_PAGE = "https://connect.garmin.com/app/settings/personalApiToken"


def _iso(day) -> str:
    return day.isoformat() if isinstance(day, date) else str(day)


class GarminPersonal:
    def __init__(self, api_key: str | None = None, client=None, token_cache: str = "/tmp/garmin-personal-token.json",
                 retries: int = 3):
        if not api_key and client is None:
            raise ValueError("Garmin Personal API key is required")
        self.api_key, self.token_cache, self.retries = api_key, token_cache, retries
        self._client = client

    @classmethod
    def from_env(cls, var: str = "GarminApiKey", **kwargs):
        return cls(os.environ.get(var), **kwargs)

    @property
    def client(self):
        if self._client is None:
            from garmin_personal_api import GarminPersonalApiClient, PersonalApiAuthenticator

            try:
                with PersonalApiAuthenticator(bearer_token_cache_file=self.token_cache) as auth:
                    token = auth.obtain_token(self.api_key)
            except Exception as e:
                if getattr(e, "status_code", None) in (401, 403):
                    raise AuthError(f"Garmin rejected the Personal API key (expired or deleted). Create a new one at {KEY_PAGE}") from e
                raise
            self._client = GarminPersonalApiClient(token.access_token)
        return self._client

    def _call(self, method: str, *args, **kwargs):
        for attempt in range(1, self.retries + 1):
            try:
                return getattr(self.client, method)(*args, **kwargs)
            except Exception as e:
                status = getattr(e, "status_code", None)
                if status in (401, 403):
                    raise AuthError(f"Garmin refused {method} ({status}); the key may have expired. {KEY_PAGE}") from e
                if status in (429, 500, 502, 503, 504) and attempt < self.retries:
                    time.sleep(2 ** attempt)
                    continue
                if status is not None:
                    raise ApiError(f"Garmin {method} failed with {status}", status) from e
                raise

    # ---- raw data
    def sleep(self, day):
        return self._call("get_daily_sleep", _iso(day))

    def sleep_range(self, start, end):
        return self._call("get_daily_sleep_summaries", _iso(start), _iso(end))

    def hrv(self, day):
        return self._call("get_daily_hrv", _iso(day))

    def hrv_range(self, start, end):
        return self._call("get_daily_hrv_summaries", _iso(start), _iso(end))

    def daily_summary(self, day):
        return self._call("get_daily_summaries", _iso(day), _iso(day))

    def daily_summaries(self, start, end):
        return self._call("get_daily_summaries", _iso(start), _iso(end))

    def stress(self, start, end):
        return self._call("get_daily_stress", _iso(start), _iso(end))

    def body_battery(self, start, end):
        return self._call("get_daily_body_battery", _iso(start), _iso(end))

    def heart_rate(self, day):
        return self._call("get_daily_heart_rate", _iso(day))

    def activities(self, start=None, end=None, limit: int = 20, activity_type: str | None = None):
        kwargs = {"start": 0, "limit": limit}
        if start:
            kwargs["start_date"] = _iso(start)
        if end:
            kwargs["end_date"] = _iso(end)
        if activity_type:
            kwargs["activity_type"] = activity_type
        return self._call("search_activities", **kwargs)

    def activity(self, activity_id: int):
        return self._call("get_activity", activity_id)

    def download_activity(self, activity_id: int) -> bytes:
        return self._call("download_activity", activity_id)


# ---- typed views over the JSON
@dataclass(frozen=True)
class SleepMetrics:
    synced: bool
    seconds: int | None
    score: int | None
    resting_hr: int | None
    avg_hrv: int | None
    body_battery_change: int | None


@dataclass(frozen=True)
class HrvMetrics:
    last_night: int | None
    weekly_avg: int | None
    baseline_low: int | None
    baseline_high: int | None
    status: str | None


@dataclass(frozen=True)
class DailyMetrics:
    resting_hr: int | None
    stress_avg: int | None
    body_battery_high: int | None
    body_battery_low: int | None


def sleep_metrics(data) -> SleepMetrics:
    """Fields are located by name, so small changes in response nesting don't break parsing."""
    seconds = to_int(find_key(data, "sleepTimeSeconds"))
    score = dig(find_key(data, "sleepScores"), "overall", "value")
    if score is None:
        score = find_key(data, "overallSleepScore") or find_key(data, "sleepScore")
    if isinstance(score, dict):
        score = score.get("value")
    return SleepMetrics(synced=bool(seconds), seconds=seconds, score=to_int(score),
                        resting_hr=to_int(find_key(data, "restingHeartRate")),
                        avg_hrv=to_int(find_key(data, "avgOvernightHrv")),
                        body_battery_change=to_int(find_key(data, "bodyBatteryChange")))


def hrv_metrics(data) -> HrvMetrics:
    summary = find_key(data, "hrvSummary") or {}
    baseline = summary.get("baseline") or {}
    return HrvMetrics(last_night=to_int(summary.get("lastNightAvg")), weekly_avg=to_int(summary.get("weeklyAvg")),
                      baseline_low=to_int(baseline.get("balancedLow")), baseline_high=to_int(baseline.get("balancedUpper")),
                      status=summary.get("status"))


def daily_metrics(data) -> DailyMetrics:
    return DailyMetrics(resting_hr=to_int(find_key(data, "restingHeartRate")),
                        stress_avg=to_int(find_key(data, "averageStressLevel")),
                        body_battery_high=to_int(find_key(data, "bodyBatteryHighestValue")),
                        body_battery_low=to_int(find_key(data, "bodyBatteryLowestValue")))
