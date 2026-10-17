"""
Centralized Timezone & Datetime Utilities (Indian Standard Time - IST)
=====================================================================
Ensures all system-generated timestamps, database records, telemetry,
and run IDs are strictly synchronized with Indian Standard Time (UTC+05:30).
"""

from datetime import datetime, timezone, timedelta

# Indian Standard Time (IST) is UTC+05:30
IST = timezone(timedelta(hours=5, minutes=30), name="IST")


def get_ist_now() -> datetime:
    """Returns current datetime in Indian Standard Time (IST, UTC+05:30) as a clean naive datetime."""
    return datetime.now(IST).replace(tzinfo=None)


def get_ist_now_aware() -> datetime:
    """Returns current datetime in Indian Standard Time (IST, UTC+05:30) as timezone-aware."""
    return datetime.now(IST)


def get_ist_timestamp_str(format_str: str = "%Y%m%d-%H%M%S") -> str:
    """Returns formatted timestamp string in IST for run IDs and filenames."""
    return datetime.now(IST).strftime(format_str)


def format_iso_ist(dt: datetime = None) -> str:
    """Returns ISO 8601 string in IST with explicit +05:30 offset."""
    if dt is None:
        return datetime.now(IST).isoformat()
    if dt.tzinfo is None:
        return dt.replace(tzinfo=IST).isoformat()
    return dt.astimezone(IST).isoformat()
