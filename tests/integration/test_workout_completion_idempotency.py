from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from hwa.db.base import Base
from hwa.db.engine import DatabaseSettings, create_engine
from hwa.db.models.identity import Person
from hwa.db.models.programme import ProgrammeDay, ProgrammeDefinition
from hwa.domain.workout import CanonicalWorkoutEventV1
from hwa.services.workout_drafts import create_draft


def _seed(session: Session) -> None:
    session.add(
        Person(
            id="hwa-kris",
            canonical_key="kris",
            display_name="Kris",
            presentation_profile="male",
            active=True,
        )
    )
    session.add(
        ProgrammeDefinition(
            programme_id="home-workout-12m-v1",
            schema_version=1,
            title="Home Workout 12 Month Programme",
            active=True,
            seed_checksum="seed",
        )
    )
    session.flush()
    session.add(
        ProgrammeDay(
            id="week1-day1",
            programme_id="home-workout-12m-v1",
            week_number=1,
            day_number=1,
            title="Upper Body + Bike",
            workout_type="upper_body_bike",
            block="foundation",
        )
    )
    session.commit()


def _event(duration_seconds: int = 600) -> CanonicalWorkoutEventV1:
    start = datetime(2026, 10, 1, 17, 0, tzinfo=UTC)
    end = start + timedelta(seconds=duration_seconds)
    return CanonicalWorkoutEventV1.model_validate(
        {
            "event_id": "event-kris-001",
            "source_event_id": "event-kris-001",
            "person_id": "hwa-kris",
            "start_at": start,
            "end_at": end,
            "duration_seconds": duration_seconds,
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


def test_duplicate_completion_creates_exactly_one_revision(tmp_path) -> None:
    from hwa.services.workout_evidence import complete_workout

    from hwa.db.models.workout import WorkoutDraft, WorkoutEvent, WorkoutRevision

    engine = create_engine(
        DatabaseSettings(database_url=f"sqlite:///{tmp_path / 'complete.db'}")
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    try:
        _seed(session)
        draft = create_draft(
            session,
            person_id="hwa-kris",
            programme_day_id="week1-day1",
            snapshot={"phase": "WORKOUT_SUMMARY", "state_data": {}},
            started_at=datetime(2026, 10, 1, 17, 0, tzinfo=UTC),
        )
        completed_at = datetime(2026, 10, 1, 17, 10, tzinfo=UTC)
        first = complete_workout(
            session,
            person_id="hwa-kris",
            draft_id=draft.id,
            idempotency_key="complete-001",
            event=_event(),
            completed_at=completed_at,
        )
        replay = complete_workout(
            session,
            person_id="hwa-kris",
            draft_id=draft.id,
            idempotency_key="complete-001",
            event=_event(),
            completed_at=completed_at,
        )

        assert first.event_id == "event-kris-001"
        assert first.revision_number == 1
        assert replay.revision_id == first.revision_id
        assert session.scalar(select(func.count()).select_from(WorkoutEvent)) == 1
        assert session.scalar(select(func.count()).select_from(WorkoutRevision)) == 1
        row = session.get(WorkoutDraft, draft.id)
        assert row is not None
        assert row.status == "COMPLETED"
    finally:
        session.close()
        engine.dispose()


def test_same_idempotency_key_with_changed_payload_fails_closed(tmp_path) -> None:
    from hwa.services.workout_evidence import IdempotencyConflict, complete_workout

    engine = create_engine(
        DatabaseSettings(database_url=f"sqlite:///{tmp_path / 'idempotency.db'}")
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    try:
        _seed(session)
        draft = create_draft(
            session,
            person_id="hwa-kris",
            programme_day_id="week1-day1",
            snapshot={"phase": "WORKOUT_SUMMARY", "state_data": {}},
            started_at=datetime(2026, 10, 1, 17, 0, tzinfo=UTC),
        )
        complete_workout(
            session,
            person_id="hwa-kris",
            draft_id=draft.id,
            idempotency_key="complete-001",
            event=_event(),
            completed_at=datetime(2026, 10, 1, 17, 10, tzinfo=UTC),
        )

        with pytest.raises(IdempotencyConflict):
            complete_workout(
                session,
                person_id="hwa-kris",
                draft_id=draft.id,
                idempotency_key="complete-001",
                event=_event(duration_seconds=660),
                completed_at=datetime(2026, 10, 1, 17, 11, tzinfo=UTC),
            )
    finally:
        session.close()
        engine.dispose()
