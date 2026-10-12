"""Input validation utilities."""

import re
from zoneinfo import ZoneInfo, available_timezones
from typing import Tuple


def validate_coordinates(latitude: float, longitude: float) -> Tuple[float, float]:
    """Validate latitude (-90 to 90) and longitude (-180 to 180)."""
    if not (-90.0 <= latitude <= 90.0):
        raise ValueError(f"Latitude must be between -90 and 90, got {latitude}")
    if not (-180.0 <= longitude <= 180.0):
        raise ValueError(f"Longitude must be between -180 and 180, got {longitude}")
    return latitude, longitude


def validate_email_address(email: str) -> str:
    """Validate email format loosely and safely."""
    email_clean = email.strip()
    if not email_clean:
        return ""
    pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    if not re.match(pattern, email_clean):
        raise ValueError(f"Invalid email address: {email_clean}")
    return email_clean


def validate_timezone_name(tz_name: str) -> str:
    """Validate that the timezone string is valid IANA timezone."""
    tz_clean = tz_name.strip()
    try:
        ZoneInfo(tz_clean)
        return tz_clean
    except Exception:
        raise ValueError(f"Invalid timezone: {tz_clean}")
