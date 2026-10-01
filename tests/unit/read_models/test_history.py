from datetime import UTC, datetime, timedelta
from decimal import Decimal

from hwa.read_models.history import get_exercise_history, get_workout_history
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from hwa.db.base import Base
from hwa.db.engine import DatabaseSettings, create_engine
from hwa.db.models.identity import Person
from hwa.db.models.programme import ProgrammeDay, ProgrammeDefinition
from hwa.db.models.workout import WorkoutEvent, WorkoutRevision
from hwa.domain.workout import CanonicalWorkoutEventV1


def _event(
    *,
    event_id: str,
    person_id: str,
    day: int,
    rpe: int,
    reps: int,
) -> CanonicalWorkoutEventV1:
    start = datetime(2026, 10, day, 17, 0, tzinfo=UTC)
    end = start + timedelta(minutes=30)
    return CanonicalWorkoutEventV1.model_validate(
        {
            "event_id": event_id,
            "source_event_id": f"source-{event_id}",
            "person_id": person_id,
            "start_at": start,
            "end_at": end,
            "duration_seconds": 1800,
            "workout_type": "strength",
            "programme": {
                "programme_id": "home-workout-12m-v1",
                "programme_week": 1,
                "programme_day": day,
                "block": "foundation",
            },
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
                                "load_value": Decimal("10.0"),
                                "load_unit": "KG",
                                "load_mode": "SINGLE_IMPLEMENT",
                                "reps": reps,
                                "duration_seconds": None,
                                "rir": 2,
                                "rpe": Decimal("7.0"),
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


def _session() -> tuple[Session, Engine]:
    engine = create_engine(DatabaseSettings(database_url="sqlite:///:memory:"))
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add_all(
        [
            Person(
                id="hwa-kris",
                canonical_key="kris",
                display_name="Kris",
                presentation_profile="male",
                active=True,
            ),
            Person(
                id="hwa-kirsty",
                canonical_key="kirsty",
                display_name="Kirsty",
                presentation_profile="female",
                active=True,
            ),
            ProgrammeDefinition(
                programme_id="home-workout-12m-v1",
                schema_version=1,
                title="Home Workout",
                active=True,
                seed_checksum="seed",
            ),
        ]
    )
    session.flush()
    for day in (1, 2):
        session.add(
            ProgrammeDay(
                id=f"week1-day{day}",
                programme_id="home-workout-12m-v1",
                week_number=1,
                day_number=day,
                title=f"Day {day}",
                workout_type="strength",
                block="foundation",
            )
        )
    session.flush()

    kris_v1 = _event(
        event_id="kris-event-1",
        person_id="hwa-kris",
        day=1,
        rpe=6,
        reps=8,
    )
    kris_v2 = _event(
        event_id="kris-event-1",
        person_id="hwa-kris",
        day=1,
        rpe=8,
        reps=10,
    )
    kirsty = _event(
        event_id="kirsty-event-1",
        person_id="hwa-kirsty",
        day=2,
        rpe=5,
        reps=7,
    )
    session.add_all(
        [
            WorkoutEvent(
                event_id="kris-event-1",
                person_id="hwa-kris",
                programme_day_id="week1-day1",
                effective_revision_number=2,
                created_at_utc=kris_v1.end_at,
            ),
            WorkoutRevision(
                id="kris-r1",
                event_id="kris-event-1",
                revision_number=1,
                supersedes_revision_number=None,
                canonical_json=kris_v1.model_dump_json(by_alias=True),
                recorded_at_utc=kris_v1.end_at,
                correction_reason=None,
            ),
            WorkoutRevision(
                id="kris-r2",
                event_id="kris-event-1",
                revision_number=2,
                supersedes_revision_number=1,
                canonical_json=kris_v2.model_dump_json(by_alias=True),
                recorded_at_utc=kris_v2.end_at + timedelta(hours=1),
                correction_reason="Correct reps and RPE",
            ),
            WorkoutEvent(
                event_id="kirsty-event-1",
                person_id="hwa-kirsty",
                programme_day_id="week1-day2",
                effective_revision_number=1,
                created_at_utc=kirsty.end_at,
            ),
            WorkoutRevision(
                id="kirsty-r1",
                event_id="kirsty-event-1",
                revision_number=1,
                supersedes_revision_number=None,
                canonical_json=kirsty.model_dump_json(by_alias=True),
                recorded_at_utc=kirsty.end_at,
                correction_reason=None,
            ),
        ]
    )
    session.commit()
    return session, engine


def test_history_returns_only_effective_revision_for_resolved_person() -> None:
    session, engine = _session()
    try:
        history = get_workout_history(session, "hwa-kris")
        assert len(history) == 1
        row = history[0]
        assert row.event_id == "kris-event-1"
        assert row.revision_number == 2
        assert row.session_rpe == Decimal("8")
        assert row.programme_week == 1
        assert row.programme_day == 1
        assert row.completed is True
        assert all(item.event_id != "kirsty-event-1" for item in history)
    finally:
        session.close()
        engine.dispose()


def test_exercise_history_uses_effective_performed_evidence() -> None:
    session, engine = _session()
    try:
        history = get_exercise_history(session, "hwa-kris", "goblet-squat")
        assert len(history) == 1
        row = history[0]
        assert row.event_id == "kris-event-1"
        assert row.revision_number == 2
        assert row.completed_sets == 1
        assert row.total_reps == 10
        assert row.max_recorded_load_kg == Decimal("10.0")
    finally:
        session.close()
        engine.dispose()
