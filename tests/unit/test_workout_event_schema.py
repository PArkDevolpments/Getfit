from datetime import UTC, datetime, timedelta
from importlib import import_module
from pathlib import Path

import pytest
from pydantic import ValidationError


def _workout():
    assert Path("src/hwa/domain/workout.py").exists(), (
        "canonical workout domain schema must exist"
    )
    return import_module("hwa.domain.workout")


def _valid_event_payload() -> dict[str, object]:
    start = datetime(2026, 10, 1, 17, 0, tzinfo=UTC)
    end = start + timedelta(minutes=42, seconds=30)
    return {
        "event_id": "workout-1",
        "source_event_id": "workout-1",
        "person_id": "person_a",
        "start_at": start,
        "end_at": end,
        "duration_seconds": 2550,
        "workout_type": "upper_body_bike",
        "programme": {
            "programme_id": "home-workout-12m-v1",
            "programme_week": 1,
            "programme_day": 1,
            "block": "foundation",
        },
        "effort": {"session_rpe": 6.5},
        "heart_rate_response": {"status": "UNAVAILABLE"},
        "training_load": {"status": "UNAVAILABLE"},
        "performance": {"completed": True, "strength": [], "cardio": []},
        "provenance": {
            "authority": "HOME_WORKOUT_ASSISTANT",
            "source_instance": "home-workout-assistant",
            "recorded_at": end,
        },
    }


def test_valid_canonical_event_has_fixed_schema_identity() -> None:
    module = _workout()
    event = module.CanonicalWorkoutEventV1.model_validate(_valid_event_payload())
    assert event.model_dump(by_alias=True)["schema"] == (
        "home-workout-assistant.workout-event"
    )
    assert event.schema_version == 1
    assert event.duration_seconds == 2550
    assert event.effort.session_rpe == 6.5


def test_canonical_event_rejects_naive_timestamp() -> None:
    module = _workout()
    payload = _valid_event_payload()
    payload["start_at"] = datetime(2026, 10, 1, 17, 0)
    with pytest.raises(ValidationError):
        module.CanonicalWorkoutEventV1.model_validate(payload)


def test_canonical_event_rejects_end_before_start() -> None:
    module = _workout()
    payload = _valid_event_payload()
    payload["end_at"] = datetime(2026, 10, 1, 16, 0, tzinfo=UTC)
    with pytest.raises(ValidationError):
        module.CanonicalWorkoutEventV1.model_validate(payload)


def test_canonical_event_rejects_duration_inconsistent_with_timestamps() -> None:
    module = _workout()
    payload = _valid_event_payload()
    payload["duration_seconds"] = 60
    with pytest.raises(ValidationError):
        module.CanonicalWorkoutEventV1.model_validate(payload)


def test_session_rpe_must_be_between_one_and_ten() -> None:
    module = _workout()
    payload = _valid_event_payload()
    payload["effort"] = {"session_rpe": 10.1}
    with pytest.raises(ValidationError):
        module.CanonicalWorkoutEventV1.model_validate(payload)
