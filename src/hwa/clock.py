"""Timezone-safe clock conversion helpers."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from hwa.config import settings


def require_aware(value: datetime) -> datetime:
    """Reject naive datetimes at application boundaries."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value


def to_utc(value: datetime) -> datetime:
    """Normalize an aware datetime to UTC."""

    return require_aware(value).astimezone(timezone.utc)


def to_household_time(value: datetime) -> datetime:
    """Render an aware datetime in the configured household timezone."""

    return require_aware(value).astimezone(ZoneInfo(settings.household_timezone))
