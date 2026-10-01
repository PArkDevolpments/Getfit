from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from hwa.db.base import Base
from hwa.db.engine import DatabaseSettings, create_engine
from hwa.db.models.identity import Person
from hwa.db.models.programme import ProgrammeDay, ProgrammeDefinition
from hwa.db.models.workout import WorkoutEvent, WorkoutRevision
from hwa.domain.workout import CanonicalWorkoutEventV1
from hwa.read_models.progress import get_progress_summary


def _event(event_id: str, person_id: str, day: int) -> CanonicalWorkoutEventV1:
    start = datetime(2026, 10, day, 17, 0, tzinfo=UTC)
    end = start + timedelta(minutes=20)
    return CanonicalWorkoutEventV1.model_validate(
        {
            "event_id": event_id,
            "source_event_id": f"source-{event_id}",
            "person_id": person_id,
            "start_at": start,
            "end_at": end,
            "duration_seconds": 1200,
            "workout_type": "mixed",
            "programme": {
                "programme_id": "home-workout-12m-v1",
                "programme_week": 1,
                "programme_day": day,
                "block": "foundation",
            },
            "effort": {"session_rpe": 6},
            "heart_rate_response": {"status": "UNAVAILABLE"},
            "training_load": {"status": "UNAVAILABLE"},
            "performance": {"completed": True, "strength": [], "cardio": []},
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
    for day in (1, 2, 3, 4):
        session.add(
            ProgrammeDay(
                id=f"week1-day{day}",
                programme_id="home-workout-12m-v1",
                week_number=1,
                day_number=day,
                title=f"Day {day}",
                workout_type="mixed",
                block="foundation",
            )
        )
    session.flush()
    for event_id, person_id, day in (
        ("kris-1", "hwa-kris", 1),
        ("kris-2", "hwa-kris", 2),
        ("kirsty-1", "hwa-kirsty", 3),
    ):
        event = _event(event_id, person_id, day)
        session.add(
            WorkoutEvent(
                event_id=event_id,
                person_id=person_id,
                programme_day_id=f"week1-day{day}",
                effective_revision_number=1,
                created_at_utc=event.end_at,
            )
        )
        session.add(
            WorkoutRevision(
                id=f"revision-{event_id}",
                event_id=event_id,
                revision_number=1,
                supersedes_revision_number=None,
                canonical_json=event.model_dump_json(by_alias=True),
                recorded_at_utc=event.end_at,
                correction_reason=None,
            )
        )
    session.commit()
    return session, engine


def test_progress_summary_is_person_scoped_and_descriptive() -> None:
    session, engine = _session()
    try:
        summary = get_progress_summary(session, "hwa-kris")
        assert summary.completed_workouts == 2
        assert summary.available_programme_workouts == 4
        assert summary.completion_percent == 50
        assert summary.latest_programme_week == 1
        assert summary.latest_programme_day == 2
        assert not hasattr(summary, "readiness")
        assert not hasattr(summary, "health_status")
    finally:
        session.close()
        engine.dispose()


def test_progress_summary_does_not_borrow_another_persons_workouts() -> None:
    session, engine = _session()
    try:
        summary = get_progress_summary(session, "hwa-kirsty")
        assert summary.completed_workouts == 1
        assert summary.latest_programme_day == 3
    finally:
        session.close()
        engine.dispose()
