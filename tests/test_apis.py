import sys
import time
import types

import pytest

from cu_commons.apis import garmin, openmeteo, strava
from cu_commons.errors import ApiError, AuthError, NoDataError

SLEEP = {"dailySleepDTO": {"sleepTimeSeconds": 27600, "sleepScores": {"overall": {"value": 84}}},
         "restingHeartRate": 49, "avgOvernightHrv": 51, "bodyBatteryChange": 62}
HRV = {"hrvSummary": {"lastNightAvg": 52, "weeklyAvg": 50, "status": "BALANCED",
                      "baseline": {"balancedLow": 45, "balancedUpper": 55}}}


def test_garmin_metrics_known_and_other_shapes():
    s = garmin.sleep_metrics(SLEEP)
    assert (s.synced, s.seconds, s.score, s.resting_hr, s.body_battery_change) == (True, 27600, 84, 49, 62)
    other = garmin.sleep_metrics({"items": [{"sleepTimeSeconds": 25200, "overallSleepScore": {"value": 77}}]})
    assert (other.seconds, other.score) == (25200, 77)
    assert garmin.sleep_metrics({}).synced is False
    h = garmin.hrv_metrics(HRV)
    assert (h.last_night, h.baseline_low, h.baseline_high, h.status) == (52, 45, 55, "BALANCED")
    d = garmin.daily_metrics([{"restingHeartRate": 48, "averageStressLevel": 30}])
    assert (d.resting_hr, d.stress_avg) == (48, 30)


class HttpError(Exception):
    def __init__(self, status):
        super().__init__(status)
        self.status_code = status


def test_garmin_retries_then_maps_auth(monkeypatch):
    monkeypatch.setattr(garmin.time, "sleep", lambda s: None)
    calls = []

    class Client:
        def get_daily_hrv(self, day):
            calls.append(day)
            if len(calls) == 1:
                raise HttpError(429)
            return HRV

        def get_daily_sleep(self, day):
            raise HttpError(401)

        def search_activities(self, **kw):
            return kw

    g = garmin.GarminPersonal(client=Client())
    assert g.hrv("2026-11-12") == HRV and calls == ["2026-11-12", "2026-11-12"]
    with pytest.raises(AuthError):
        g.sleep("2026-11-12")
    assert g.activities("2026-11-01", limit=5) == {"start": 0, "limit": 5, "start_date": "2026-11-01"}


def test_garmin_rejected_key(monkeypatch):
    class Auth:
        def __init__(self, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def obtain_token(self, key):
            raise HttpError(401)

    fake = types.ModuleType("garmin_personal_api")
    fake.PersonalApiAuthenticator, fake.GarminPersonalApiClient = Auth, object
    monkeypatch.setitem(sys.modules, "garmin_personal_api", fake)
    with pytest.raises(AuthError):
        garmin.GarminPersonal(api_key="bad").client
    with pytest.raises(ValueError):
        garmin.GarminPersonal()


def test_strava_refresh_rotation_and_cache(monkeypatch):
    rotated, calls = [], []

    def fake(method, url, **kw):
        calls.append(url)
        if url == strava.TOKEN_URL:
            return {"access_token": "A1", "expires_at": int(time.time()) + 3600, "refresh_token": "R2"}
        if url.endswith("/athlete/activities"):
            return [{"id": 1, "sport_type": "Ride"}, {"id": 2, "sport_type": "Run"}]
        return {"id": 2, "url": url, "auth": kw["headers"]["Authorization"]}

    monkeypatch.setattr(strava, "request_json", fake)
    client = strava.StravaClient("id", "secret", "R1", on_refresh=rotated.append)
    run = client.latest()
    assert run["id"] == 2 and run["auth"] == "Bearer A1"
    assert rotated == ["R2"] and client.refresh_token == "R2"
    assert calls.count(strava.TOKEN_URL) == 1  # token cached for the second call


def test_strava_bad_refresh_and_no_run(monkeypatch):
    def refuse(method, url, **kw):
        raise ApiError("bad", 400)

    monkeypatch.setattr(strava, "request_json", refuse)
    with pytest.raises(AuthError):
        strava.StravaClient("id", "secret", "R1").athlete()
    monkeypatch.setattr(strava, "request_json", lambda m, url, **kw: [] if "activities" in url else
                        {"access_token": "A", "expires_at": int(time.time()) + 3600})
    with pytest.raises(NoDataError):
        strava.StravaClient("id", "secret", "R1").latest()


def test_openmeteo(monkeypatch):
    seen = {}
    monkeypatch.setattr(openmeteo, "request_json", lambda m, url, **kw: seen.update(url=url, **kw) or {})
    openmeteo.air_quality(28.46, 77.03)
    assert seen["params"]["hourly"] == "us_aqi,pm2_5" and seen["params"]["timezone"] == "Asia/Kolkata"
    hours = [f"2026-11-12T{h:02d}:00" for h in range(24)]
    data = {"hourly": {"time": hours, "us_aqi": list(range(24))}}
    assert openmeteo.hourly_values(data, "us_aqi", range(5, 10)) == [5, 6, 7, 8, 9]
