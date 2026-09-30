from datetime import UTC, datetime, timedelta

import pytest

from hwa.domain.identity import PersonContext
from hwa.domain.workout import CanonicalWorkoutEventV1
from hwa.services.workout_evidence import WorkoutRevisionRecord


def _context(hwa_person_id: str = "hwa-kris") -> PersonContext:
    return PersonContext(
        hwa_person_id=hwa_person_id,
        pep_person_id="person_a",
        health_profile_id="kris",
        menu_person_id="person_1",
        presentation_profile="male",
        display_name="Kris",
    )


def _event(person_id: str = "hwa-kris") -> CanonicalWorkoutEventV1:
    start = datetime(2026, 10, 1, 17, 0, tzinfo=UTC)
    end = start + timedelta(minutes=10)
    return CanonicalWorkoutEventV1.model_validate(
        {
            "event_id": "event-001",
            "source_event_id": "event-001",
            "person_id": person_id,
            "start_at": start,
            "end_at": end,
            "duration_seconds": 600,
            "workout_type": "upper_body_bike",
            "programme": {
                "programme_id": "home-workout-12m-v1",
                "programme_week": 1,
                "programme_day": 1,
                "block": "foundation",
            },
            "effort": {"session_rpe": 6},
            "heart_rate_response": {"status": "UNAVAILABLE"},
            "training_load": {"status": "UNAVAILABLE"},
            "performance": {"completed": True, "strength": [], "cardio": []},
            "provenance": {
                "authority": "HOME_WORKOUT_ASSISTANT",
                "source_instance": "home-workout-assistant",
                "recorded_at": end,
            },
        }
    )


def _revision(number: int = 1) -> WorkoutRevisionRecord:
    return WorkoutRevisionRecord(
        revision_id=f"revision-{number}",
        event_id="event-001",
        revision_number=number,
        supersedes_revision_number=number - 1 if number > 1 else None,
        event=_event(),
        recorded_at=datetime(2026, 10, 1, 17, 10, tzinfo=UTC),
        correction_reason="correction" if number > 1 else None,
    )


def test_pep_projection_uses_explicit_cross_system_person_and_provenance() -> None:
    from hwa.integrations.pep.workout_projection import project_workout_for_pep

    projected = project_workout_for_pep(_context(), _revision())
    payload = projected.model_dump(mode="json", by_alias=True)

    assert payload["schema"] == "home-workout-assistant.pep-workout-projection"
    assert payload["schema_version"] == 1
    assert payload["person_id"] == "person_a"
    assert payload["hwa_person_id"] == "hwa-kris"
    assert payload["event_id"] == "event-001"
    assert payload["revision_number"] == 1
    assert payload["duration_seconds"] == 600
    assert payload["session_rpe"] == "6"
    assert payload["provenance"]["source_authority"] == "HOME_WORKOUT_ASSISTANT"
    assert payload["provenance"]["atomic_evidence_id"] == "revision-1"


def test_projection_does_not_invent_ambiguous_pep_duration_or_effort_fields() -> None:
    from hwa.integrations.pep.workout_projection import project_workout_for_pep

    payload = project_workout_for_pep(_context(), _revision()).model_dump(
        mode="json", by_alias=True
    )
    assert "duration" not in payload
    assert "effort" not in payload
    assert payload["heart_rate_response"]["status"] == "UNAVAILABLE"
    assert payload["training_load"]["status"] == "UNAVAILABLE"


def test_correction_projection_keeps_logical_event_and_explicit_supersession() -> None:
    from hwa.integrations.pep.workout_projection import project_workout_for_pep

    payload = project_workout_for_pep(_context(), _revision(2)).model_dump(
        mode="json", by_alias=True
    )
    assert payload["event_id"] == "event-001"
    assert payload["revision_number"] == 2
    assert payload["supersedes_revision_number"] == 1
    assert payload["provenance"]["atomic_evidence_id"] == "revision-2"


def test_projection_rejects_cross_person_revision() -> None:
    from hwa.integrations.pep.workout_projection import PepProjectionIdentityError, project_workout_for_pep

    revision = WorkoutRevisionRecord(
        revision_id="revision-other",
        event_id="event-001",
        revision_number=1,
        supersedes_revision_number=None,
        event=_event(person_id="hwa-kirsty"),
        recorded_at=datetime(2026, 10, 1, 17, 10, tzinfo=UTC),
        correction_reason=None,
    )
    with pytest.raises(PepProjectionIdentityError):
        project_workout_for_pep(_context(), revision)
