"""Open-Meteo weather forecast and air quality (free, no API key)."""
from cu_commons.http import request_json

FORECAST = "https://api.open-meteo.com/v1/forecast"
AIR_QUALITY = "https://air-quality-api.open-meteo.com/v1/air-quality"


def forecast(lat: float, lon: float, daily=("temperature_2m_min", "temperature_2m_max", "precipitation_probability_max"),
             hourly=("temperature_2m",), tz: str = "Asia/Kolkata", days: int = 1) -> dict:
    return request_json("GET", FORECAST, timeout=15, params={
        "latitude": lat, "longitude": lon, "timezone": tz, "forecast_days": days,
        "daily": ",".join(daily), "hourly": ",".join(hourly)})


def air_quality(lat: float, lon: float, hourly=("us_aqi", "pm2_5"), tz: str = "Asia/Kolkata", days: int = 1) -> dict:
    return request_json("GET", AIR_QUALITY, timeout=15, params={
        "latitude": lat, "longitude": lon, "timezone": tz, "forecast_days": days, "hourly": ",".join(hourly)})


def hourly_values(data: dict, key: str, hours: range | None = None) -> list:
    """Values of an hourly series, optionally only for local hours in `hours` (e.g. range(5, 10))."""
    hourly = data.get("hourly") or {}
    pairs = zip(hourly.get("time") or [], hourly.get(key) or [], strict=False)
    return [v for t, v in pairs if v is not None and (hours is None or int(t[11:13]) in hours)]
