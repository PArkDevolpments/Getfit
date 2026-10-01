from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from hwa.db.base import Base
from hwa.db.engine import DatabaseSettings, create_engine
from hwa.db.models.identity import ExternalIdentityMapping, Person
from hwa.db.models.workout import WorkoutEvent, WorkoutRevision
from hwa.domain.workout import CanonicalWorkoutEventV1


def _event(*, reps: int, rpe: Decimal) -> CanonicalWorkoutEventV1:
    start = datetime(2026, 10, 1, 17, 0, tzinfo=UTC)
    end = start + timedelta(minutes=20)
    return CanonicalWorkoutEventV1.model_validate(
        {
            "event_id": "logical-1",
            "source_event_id": "draft-1",
            "person_id": "hwa-kris",
            "start_at": start,
            "end_at": end,
            "duration_seconds": 1200,
            "workout_type": "strength",
            "programme": None,
            "effort": {"session_rpe": rpe},
            "heart_rate_response": {"status": "UNAVAILABLE"},
            "training_load": {"status": "UNAVAILABLE"},
            "performance": {
                "completed": True,
                "strength": [
                    {
                        "exercise_id": "goblet-squat",
                        "completed": True,
                        "sets": [
                            {
                                "set_number": 1,
                                "laterality": "BILATERAL",
                                "target_type": "REPS",
                                "load_value": 10,
                                "load_unit": "KG",
                                "load_mode": "SINGLE_IMPLEMENT",
                                "reps": reps,
                                "duration_seconds": None,
                                "rir": 2,
                                "rpe": rpe,
                                "completed": True,
                                "pain_flag": False,
                            }
                        ],
                    }
                ],
                "cardio": [],
            },
            "provenance": {
                "authority": "HOME_WORKOUT_ASSISTANT",
                "source_instance": "getfit-test",
                "recorded_at": end,
            },
        }
    )


def _session() -> tuple[Session, object]:
    engine = create_engine(DatabaseSettings(database_url="sqlite:///:memory:"))
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add(
        Person(
            id="hwa-kris",
            canonical_key="kris",
            display_name="Kris",
            presentation_profile="male",
            active=True,
        )
    )
    session.flush()
    session.add(
        ExternalIdentityMapping(
            id="kris-pep",
            person_id="hwa-kris",
            authority="PEP_SITE",
            external_subject_id="person_a",
        )
    )
    v1 = _event(reps=8, rpe=Decimal("8.0"))
    v2 = _event(reps=10, rpe=Decimal("7.0"))
    session.add(
        WorkoutEvent(
            event_id="logical-1",
            person_id="hwa-kris",
            programme_day_id=None,
            effective_revision_number=2,
            created_at_utc=v1.end_at,
        )
    )
    session.flush()
    session.add_all(
        [
            WorkoutRevision(
                id="revision-1",
                event_id="logical-1",
                revision_number=1,
                supersedes_revision_number=None,
                canonical_json=v1.model_dump_json(by_alias=True),
                recorded_at_utc=v1.end_at,
                correction_reason=None,
            ),
            WorkoutRevision(
                id="revision-2",
                event_id="logical-1",
                revision_number=2,
                supersedes_revision_number=1,
                canonical_json=v2.model_dump_json(by_alias=True),
                recorded_at_utc=v2.end_at + timedelta(hours=1),
                correction_reason="Corrected reps and session RPE",
            ),
        ]
    )
    session.commit()
    return session, engine


def test_export_returns_only_effective_revision_and_is_repeatable() -> None:
    from hwa.integrations.pep.workout_export import export_workouts_for_pep

    session, engine = _session()
    try:
        first = export_workouts_for_pep(session, "person_a")
        second = export_workouts_for_pep(session, "person_a")

        assert first == second
        assert len(first) == 1
        row = first[0]
        assert row.event_id == "logical-1"
        assert row.revision_number == 2
        assert row.supersedes_revision_number == 1
        assert row.atomic_evidence_id == "revision-2"
        assert row.effort.session_rpe == Decimal("7.0")
        assert row.performance.strength[0].sets[0].reps == 10
    finally:
        session.close()
        engine.dispose()


def test_export_uses_stable_logical_event_and_revision_specific_evidence_identity() -> None:
    from hwa.integrations.pep.workout_export import export_workouts_for_pep

    session, engine = _session()
    try:
        row = export_workouts_for_pep(session, "person_a")[0]
        assert row.event_id == "logical-1"
        assert row.source_event_id == "draft-1"
        assert row.atomic_evidence_id == "revision-2"
        assert row.recorded_at == datetime(2026, 10, 1, 18, 20, tzinfo=UTC)
    finally:
        session.close()
        engine.dispose()
