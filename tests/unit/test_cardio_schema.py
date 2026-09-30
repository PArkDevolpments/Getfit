from importlib import import_module
from pathlib import Path

import pytest
from pydantic import ValidationError


def _workout():
    assert Path("src/hwa/domain/workout.py").exists(), "workout schema must exist"
    return import_module("hwa.domain.workout")


def _programme():
    assert Path("src/hwa/domain/programme.py").exists(), "programme schema must exist"
    return import_module("hwa.domain.programme")


def test_treadmill_accepts_speed_and_incline() -> None:
    module = _workout()
    record = module.CardioPerformance(
        equipment="TREADMILL",
        duration_seconds=1200,
        speed_kmh=5.0,
        incline_percent=4,
        rpe=5,
        completed=True,
    )
    assert record.incline_percent == 4
    assert record.speed_kmh == 5.0


def test_spin_bike_rejects_incline_and_speed() -> None:
    module = _workout()
    with pytest.raises(ValidationError):
        module.CardioPerformance(
            equipment="SPIN_BIKE",
            duration_seconds=900,
            incline_percent=3,
            cadence_rpm_min=80,
            cadence_rpm_max=90,
            rpe=5,
            completed=True,
        )
    with pytest.raises(ValidationError):
        module.CardioPerformance(
            equipment="SPIN_BIKE",
            duration_seconds=900,
            speed_kmh=20,
            cadence_rpm_min=80,
            cadence_rpm_max=90,
            rpe=5,
            completed=True,
        )


def test_treadmill_rejects_bike_specific_fields() -> None:
    module = _workout()
    with pytest.raises(ValidationError):
        module.CardioPerformance(
            equipment="TREADMILL",
            duration_seconds=900,
            speed_kmh=5,
            cadence_rpm_min=80,
            resistance="moderate",
            completed=True,
        )


def test_spin_bike_cadence_range_is_preserved() -> None:
    module = _workout()
    record = module.CardioPerformance(
        equipment="SPIN_BIKE",
        duration_seconds=900,
        cadence_rpm_min=80,
        cadence_rpm_max=90,
        resistance="moderate",
        rpe=5,
        completed=True,
    )
    assert (record.cadence_rpm_min, record.cadence_rpm_max) == (80, 90)


def test_unavailable_hr_and_training_load_remain_empty() -> None:
    module = _workout()
    hr = module.HeartRateResponse(status="UNAVAILABLE")
    load = module.TrainingLoad(status="UNAVAILABLE")
    assert hr.average_bpm is None
    assert hr.maximum_bpm is None
    assert hr.recovery_bpm is None
    assert load.strength_volume_kg is None
    assert load.cardio_duration_seconds is None


def test_unavailable_hr_rejects_fabricated_measurement() -> None:
    module = _workout()
    with pytest.raises(ValidationError):
        module.HeartRateResponse(status="UNAVAILABLE", average_bpm=120)


def test_programme_spin_bike_structurally_rejects_incline() -> None:
    module = _programme()
    with pytest.raises(ValidationError):
        module.CardioPrescription(
            sequence=1,
            equipment="SPIN_BIKE",
            segment_type="STEADY",
            target_mode="RANGE",
            duration_seconds=900,
            cadence_rpm_min=80,
            cadence_rpm_max=90,
            incline_percent=2,
        )


def test_calibration_treadmill_allows_unassigned_speed_and_incline() -> None:
    module = _programme()
    target = module.CardioPrescription(
        sequence=1,
        equipment="TREADMILL",
        segment_type="STEADY",
        target_mode="CALIBRATION",
        duration_seconds=1200,
        rpe_min=5,
        rpe_max=5,
    )
    assert target.speed_kmh is None
    assert target.incline_percent is None
