from pathlib import Path

from hwa.domain.programme import TargetMode
from hwa.domain.workout import Laterality, LoadMode, TargetType

SEED = Path("programme_seed/home-workout-12m-v1/week-01.json")


def _load_week():
    from hwa.services.programmes import load_week_seed

    assert SEED.exists(), "approved Week 1 seed must exist"
    return load_week_seed(SEED)


def test_week1_has_four_approved_days() -> None:
    week = _load_week()
    assert week.week_number == 1
    assert [day.workout_type for day in week.days] == [
        "upper_body_bike",
        "lower_body_core",
        "full_body_bike",
        "conditioning",
    ]


def test_day2_uses_supported_reverse_lunge_and_timed_core() -> None:
    day = _load_week().days[1]
    by_id = {item.exercise_id: item for item in day.strength}

    lunge = by_id["supported_reverse_lunge"]
    assert lunge.target_type is TargetType.REPS
    assert lunge.reps_target == 8
    assert lunge.laterality is Laterality.EACH_SIDE
    assert lunge.load_mode is LoadMode.BODYWEIGHT

    dead_bug = by_id["dead_bug"]
    assert dead_bug.reps_target == 8
    assert dead_bug.laterality is Laterality.EACH_SIDE

    plank = by_id["forearm_plank"]
    assert plank.target_type is TargetType.DURATION
    assert plank.duration_seconds_target == 20
    assert plank.reps_target is None


def test_day4_uses_conservative_30_90_bike_intervals() -> None:
    day = _load_week().days[3]
    hard = next(item for item in day.cardio if item.segment_type == "INTERVAL_HARD")
    recovery = next(
        item for item in day.cardio if item.segment_type == "INTERVAL_RECOVERY"
    )

    assert hard.rounds == recovery.rounds == 5
    assert hard.duration_seconds == 30
    assert recovery.duration_seconds == 90
    assert (hard.cadence_rpm_min, hard.cadence_rpm_max) == (85, 100)
    assert (recovery.cadence_rpm_min, recovery.cadence_rpm_max) == (60, 75)
    assert hard.resistance is None


def test_day4_treadmill_is_steady_calibration_not_intervals() -> None:
    day = _load_week().days[3]
    treadmill = [item for item in day.cardio if item.equipment.value == "TREADMILL"]
    steady = next(item for item in treadmill if item.segment_type == "STEADY")

    assert steady.duration_seconds == 1200
    assert steady.target_mode is TargetMode.CALIBRATION
    assert steady.speed_kmh is None
    assert steady.incline_percent is None
    assert all("INTERVAL" not in item.segment_type for item in treadmill)


def test_all_spin_bike_prescriptions_have_no_incline() -> None:
    week = _load_week()
    bike_items = [
        item
        for day in week.days
        for item in day.cardio
        if item.equipment.value == "SPIN_BIKE"
    ]
    assert bike_items
    assert all(item.incline_percent is None for item in bike_items)


def test_kris_overrides_preserve_load_semantics_and_kirsty_has_none() -> None:
    week = _load_week()
    kris = week.person_overrides["kris"]
    lookup = {(item.day_number, item.exercise_id): item for item in kris}

    assert lookup[(1, "dumbbell_floor_press")].load_value == 6
    assert lookup[(1, "dumbbell_floor_press")].load_mode is LoadMode.EACH_HAND
    assert lookup[(1, "one_arm_dumbbell_row")].load_value == 10
    assert lookup[(1, "one_arm_dumbbell_row")].load_mode is LoadMode.SINGLE_IMPLEMENT
    assert lookup[(1, "overhead_triceps_extension")].load_value == 8
    assert lookup[(1, "overhead_triceps_extension")].load_mode is LoadMode.TOTAL_EXTERNAL
    assert "kirsty" not in week.person_overrides
