"""Date and duration helpers (stdlib zoneinfo; default time zone Asia/Kolkata)."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

DEFAULT_TZ = "Asia/Kolkata"


def now(tz: str = DEFAULT_TZ) -> datetime:
    return datetime.now(ZoneInfo(tz))


def today(tz: str = DEFAULT_TZ) -> date:
    return now(tz).date()


def from_timestamp(ts: float, tz: str = DEFAULT_TZ) -> datetime:
    """Unix seconds (or milliseconds, auto-detected) -> aware datetime in `tz`."""
    if ts > 1e11:
        ts = ts / 1000
    return datetime.fromtimestamp(ts, ZoneInfo(tz))


def hm(seconds: float | None) -> str:
    """7260 -> '2h 01m'; 45 -> '0h 00m'; None -> '-'."""
    if seconds is None:
        return "-"
    seconds = int(seconds)
    return f"{seconds // 3600}h {seconds % 3600 // 60:02d}m"


def pace(speed_mps: float | None) -> str:
    """Running pace per km from metres/second: 3.333 -> "5'00\"/km"."""
    if not speed_mps or speed_mps <= 0:
        return "-"
    total = round(1000 / speed_mps)
    return f"{total // 60}'{total % 60:02d}\"/km"
