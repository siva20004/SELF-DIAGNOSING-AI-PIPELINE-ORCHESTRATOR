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


def normalize_date_val(val: object) -> str:
    """
    Intelligently converts any date string or object into standard ISO YYYY-MM-DD.
    Handles:
    - US format (M/D/YYYY, MM/DD/YYYY) e.g. 5/31/2025 -> 2025-05-31
    - UK/EU/IN format (D/M/YYYY, DD/MM/YYYY) e.g. 31/05/2025 -> 2025-05-31
    - Hyphen/dot variations (DD-MM-YYYY, YYYY.MM.DD, etc.)
    - PDF text artifacts (e.g. 'D 5/31/2025', 'D 2025-05-31')
    - Timestamp components (e.g. '2025-05-31 14:30:00', '2025-05-31T00:00:00')
    """
    if val is None:
        return ""
    import re
    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", "null", ""):
        return ""

    # Strip PDF table border artifacts like 'D ', 'd ', leading letters
    s = re.sub(r"^[^\d]+", "", s).strip()
    # Strip time component if separated by space or T
    s = re.split(r"[\sT]", s)[0]

    # Already valid ISO YYYY-MM-DD
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s

    # Try explicit YYYY/MM/DD or YYYY.MM.DD
    m_ymd = re.match(r"^(\d{4})[/\-\.](\d{1,2})[/\-\.](\d{1,2})$", s)
    if m_ymd:
        y, m, d = int(m_ymd.group(1)), int(m_ymd.group(2)), int(m_ymd.group(3))
        try:
            return datetime(y, m, d).strftime("%Y-%m-%d")
        except Exception:
            pass

    # Try D/M/Y or M/D/Y (1-2 digit month/day, 2-4 digit year)
    m_dmy = re.match(r"^(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})$", s)
    if m_dmy:
        p1, p2, p3 = int(m_dmy.group(1)), int(m_dmy.group(2)), int(m_dmy.group(3))
        if p3 < 100:
            p3 += 2000
        if p1 > 12:  # p1 must be day, p2 is month
            day, month, year = p1, p2, p3
        elif p2 > 12:  # p2 must be day, p1 is month
            month, day, year = p1, p2, p3
        else:
            month, day, year = p1, p2, p3
        try:
            return datetime(year, month, day).strftime("%Y-%m-%d")
        except Exception:
            try:
                return datetime(year, day, month).strftime("%Y-%m-%d")
            except Exception:
                pass

    # Fallback with dateutil parser if available
    try:
        from dateutil import parser as date_parser
        dt = date_parser.parse(s, dayfirst=False)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        pass

    try:
        from dateutil import parser as date_parser
        dt = date_parser.parse(s, dayfirst=True)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        pass

    return s
