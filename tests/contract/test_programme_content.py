from pathlib import Path

from hwa.programmes.loader import load_week_file
from hwa.programmes.validator import validate_programme_week

WEEK_1 = Path("programme_seed/home-workout-12m-v1/week-01.json")


def test_approved_week_one_validates_without_generated_content() -> None:
    week = validate_programme_week(load_week_file(WEEK_1))
    assert week.programme_id == "home-workout-12m-v1"
    assert week.week_number == 1
    assert [day.day_number for day in week.days] == [1, 2, 3, 4]
    assert len(week.days) == 4


def test_approved_day_four_structure_is_preserved_exactly() -> None:
    week = validate_programme_week(load_week_file(WEEK_1))
    day = next(item for item in week.days if item.day_number == 4)
    assert day.title == "Conditioning"
    assert day.strength == ()

    hard = next(item for item in day.cardio if item.segment_type == "INTERVAL_HARD")
    recovery = next(
        item for item in day.cardio if item.segment_type == "INTERVAL_RECOVERY"
    )
    steady = next(
        item
        for item in day.cardio
        if item.equipment.value == "TREADMILL" and item.segment_type == "STEADY"
    )

    assert hard.equipment.value == "SPIN_BIKE"
    assert hard.rounds == 5
    assert hard.duration_seconds == 30
    assert hard.incline_percent is None
    assert hard.speed_kmh is None
    assert recovery.rounds == 5
    assert recovery.duration_seconds == 90
    assert steady.duration_seconds == 1200
    assert steady.target_mode.value == "CALIBRATION"


def test_all_week_one_spin_bike_segments_have_no_speed_or_incline() -> None:
    week = validate_programme_week(load_week_file(WEEK_1))
    bike_segments = [
        segment
        for day in week.days
        for segment in day.cardio
        if segment.equipment.value == "SPIN_BIKE"
    ]
    assert bike_segments
    assert all(segment.speed_kmh is None for segment in bike_segments)
    assert all(segment.incline_percent is None for segment in bike_segments)


def test_repository_contains_only_approved_week_files() -> None:
    week_files = sorted(Path("programme_seed/home-workout-12m-v1").glob("week-*.json"))
    assert week_files == [WEEK_1]
