from datetime import UTC, datetime, timedelta, timezone

import pytest

from hwa.clock import require_aware, to_household_time, to_utc


def test_naive_timestamp_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        require_aware(datetime(2026, 10, 1, 18, 0))


def test_offset_timestamp_normalizes_to_utc() -> None:
    value = datetime.fromisoformat("2026-10-01T18:00:00+01:00")
    assert to_utc(value) == datetime(2026, 10, 1, 17, 0, tzinfo=UTC)


def test_equivalent_instants_normalize_identically() -> None:
    london = datetime.fromisoformat("2026-10-01T18:00:00+01:00")
    utc = datetime.fromisoformat("2026-10-01T17:00:00+00:00")
    assert to_utc(london) == to_utc(utc)


def test_household_time_handles_spring_dst_transition() -> None:
    before = datetime(2026, 3, 29, 0, 30, tzinfo=UTC)
    after = datetime(2026, 3, 29, 1, 30, tzinfo=UTC)
    assert to_household_time(before).isoformat() == "2026-03-29T00:30:00+00:00"
    assert to_household_time(after).isoformat() == "2026-03-29T02:30:00+01:00"


def test_household_time_handles_autumn_dst_transition() -> None:
    first = datetime(2026, 10, 25, 0, 30, tzinfo=UTC)
    second = datetime(2026, 10, 25, 1, 30, tzinfo=UTC)
    assert to_household_time(first).isoformat() == "2026-10-25T01:30:00+01:00"
    assert to_household_time(second).isoformat() == "2026-10-25T01:30:00+00:00"


def test_non_utc_fixed_offset_is_accepted() -> None:
    value = datetime(2026, 1, 15, 12, 0, tzinfo=timezone(timedelta(hours=2)))
    assert require_aware(value) is value
