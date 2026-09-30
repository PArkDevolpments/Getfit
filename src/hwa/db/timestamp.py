"""SQLAlchemy datetime type that persists normalized UTC instants."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator

from hwa.clock import require_aware, to_utc


class UTCDateTime(TypeDecorator[datetime]):
    """Persist UTC as naive SQLite values and restore aware UTC values."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        normalized = to_utc(require_aware(value))
        return normalized.replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc)
        return value.replace(tzinfo=timezone.utc)
