"""Time and timezone utility helpers."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Optional


def get_timezone(tz_name: str) -> ZoneInfo:
    """Safely obtain ZoneInfo, falling back to UTC on invalid zone."""
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("UTC")


def now_utc() -> datetime:
    """Return the current time in UTC with timezone awareness."""
    return datetime.now(timezone.utc)


def now_in_timezone(tz_name: str = "Asia/Kolkata") -> datetime:
    """Return the current time in the specified timezone."""
    return datetime.now(get_timezone(tz_name))


def to_timezone(dt: datetime, tz_name: str = "Asia/Kolkata") -> datetime:
    """Convert an existing datetime to target timezone. If naive, assume UTC first."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(get_timezone(tz_name))


def parse_datetime(dt_str: str, default_tz_name: str = "Asia/Kolkata") -> datetime:
    """Parse an ISO string into timezone-aware datetime."""
    # Handle possible spaces or missing timezone
    clean_str = dt_str.strip().replace(" ", "T")
    dt = datetime.fromisoformat(clean_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=get_timezone(default_tz_name))
    return dt


def format_iso(dt: datetime) -> str:
    """Format datetime to standard ISO string."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def format_display_time(dt: datetime, tz_name: str = "Asia/Kolkata") -> str:
    """Format datetime for display in logs and emails."""
    local_dt = to_timezone(dt, tz_name)
    return local_dt.strftime("%Y-%m-%d %H:%M %Z")
