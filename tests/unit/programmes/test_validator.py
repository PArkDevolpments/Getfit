from copy import deepcopy

import pytest
from hwa.programmes.schema import ProgrammeWeekDocument
from hwa.programmes.validator import ProgrammeValidationError, validate_programme_week
from pydantic import ValidationError


def _day(day_number: int) -> dict[str, object]:
    return {
        "programme_id": "home-workout-12m-v1",
        "week_number": 1,
        "day_number": day_number,
        "title": f"Day {day_number}",
        "workout_type": "strength",
        "block": "foundation",
        "strength": [
            {
                "sequence": 1,
                "exercise_id": f"exercise_{day_number}",
                "target_type": "REPS",
                "sets_target": 2,
                "reps_target": 10,
                "laterality": "BILATERAL",
                "load_mode": "BODYWEIGHT",
            }
        ],
        "cardio": [],
    }


def _week() -> dict[str, object]:
    return {
        "programme_id": "home-workout-12m-v1",
        "schema_version": 1,
        "week_number": 1,
        "days": [_day(number) for number in range(1, 5)],
        "person_overrides": {},
    }


def test_valid_week_requires_four_unique_training_days() -> None:
    document = ProgrammeWeekDocument.model_validate(_week())
    validated = validate_programme_week(document)
    assert [day.day_number for day in validated.days] == [1, 2, 3, 4]


def test_incomplete_week_is_rejected_instead_of_fabricated() -> None:
    payload = _week()
    payload["days"] = [_day(number) for number in range(1, 4)]
    document = ProgrammeWeekDocument.model_validate(payload)
    with pytest.raises(ProgrammeValidationError, match="four"):
        validate_programme_week(document)


def test_unknown_fields_are_rejected_by_schema() -> None:
    payload = _week()
    payload["invented_target"] = 123
    with pytest.raises(ValidationError):
        ProgrammeWeekDocument.model_validate(payload)


def test_spin_bike_cannot_gain_treadmill_speed_or_incline() -> None:
    payload = _week()
    day = deepcopy(payload["days"][0])
    day["cardio"] = [
        {
            "sequence": 1,
            "equipment": "SPIN_BIKE",
            "segment_type": "STEADY",
            "target_mode": "CALIBRATION",
            "duration_seconds": 300,
            "speed_kmh": 4.0,
            "incline_percent": 3.0,
        }
    ]
    payload["days"][0] = day
    with pytest.raises(ValidationError):
        ProgrammeWeekDocument.model_validate(payload)


def test_duplicate_item_sequence_is_rejected() -> None:
    payload = _week()
    day = deepcopy(payload["days"][0])
    item = deepcopy(day["strength"][0])
    item["exercise_id"] = "other_exercise"
    day["strength"].append(item)
    payload["days"][0] = day
    document = ProgrammeWeekDocument.model_validate(payload)
    with pytest.raises(ProgrammeValidationError, match="sequence"):
        validate_programme_week(document)


def test_override_must_reference_an_existing_day_exercise() -> None:
    payload = _week()
    payload["person_overrides"] = {
        "kris": [
            {
                "day_number": 1,
                "exercise_id": "not_in_day",
                "load_value": 8,
                "load_unit": "KG",
                "load_mode": "SINGLE_IMPLEMENT",
            }
        ]
    }
    document = ProgrammeWeekDocument.model_validate(payload)
    with pytest.raises(ProgrammeValidationError, match="override"):
        validate_programme_week(document)
