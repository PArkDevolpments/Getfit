from datetime import datetime, timezone

import pytest

from hwa.db.timestamp import UTCDateTime


def test_sqlite_bind_rejects_naive_datetime() -> None:
    type_ = UTCDateTime()
    with pytest.raises(ValueError, match="timezone-aware"):
        type_.process_bind_param(datetime(2026, 10, 1, 18, 0), dialect=None)


def test_sqlite_bind_normalizes_to_naive_utc_storage() -> None:
    type_ = UTCDateTime()
    bound = type_.process_bind_param(
        datetime.fromisoformat("2026-10-01T18:00:00+01:00"), dialect=None
    )
    assert bound == datetime(2026, 10, 1, 17, 0)
    assert bound.tzinfo is None


def test_sqlite_result_is_restored_as_aware_utc() -> None:
    type_ = UTCDateTime()
    value = type_.process_result_value(datetime(2026, 10, 1, 17, 0), dialect=None)
    assert value == datetime(2026, 10, 1, 17, 0, tzinfo=timezone.utc)
