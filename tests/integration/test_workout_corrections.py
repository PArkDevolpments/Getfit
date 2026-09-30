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
                title="Home Workout 12 Month Programme",
                active=True,
                seed_checksum="seed",
            ),
        ]
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


def _event(session_rpe: int) -> CanonicalWorkoutEventV1:
    start = datetime(2026, 10, 1, 17, 0, tzinfo=UTC)
    end = start + timedelta(minutes=10)
    return CanonicalWorkoutEventV1.model_validate(
        {
            "event_id": "event-kris-001",
            "source_event_id": "event-kris-001",
            "person_id": "hwa-kris",
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
            "effort": {"session_rpe": session_rpe},
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


def _completed(session: Session) -> None:
    from hwa.services.workout_evidence import complete_workout

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
        event=_event(6),
        completed_at=datetime(2026, 10, 1, 17, 10, tzinfo=UTC),
    )


def test_correction_appends_revision_and_preserves_original(tmp_path) -> None:
    from hwa.db.models.workout import WorkoutEvent, WorkoutRevision
    from hwa.services.workout_evidence import correct_workout, get_effective_workout

    engine = create_engine(
        DatabaseSettings(database_url=f"sqlite:///{tmp_path / 'correction.db'}")
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    try:
        _seed(session)
        _completed(session)
        original = session.scalar(
            select(WorkoutRevision).where(WorkoutRevision.revision_number == 1)
        )
        assert original is not None
        original_json = original.canonical_json

        corrected = correct_workout(
            session,
            person_id="hwa-kris",
            event_id="event-kris-001",
            idempotency_key="correct-001",
            event=_event(7),
            reason="Correct session RPE",
            corrected_at=datetime(2026, 10, 1, 18, 0, tzinfo=UTC),
        )
        replay = correct_workout(
            session,
            person_id="hwa-kris",
            event_id="event-kris-001",
            idempotency_key="correct-001",
            event=_event(7),
            reason="Correct session RPE",
            corrected_at=datetime(2026, 10, 1, 18, 0, tzinfo=UTC),
        )

        assert corrected.revision_number == 2
        assert corrected.supersedes_revision_number == 1
        assert replay.revision_id == corrected.revision_id
        assert session.scalar(select(func.count()).select_from(WorkoutRevision)) == 2
        session.refresh(original)
        assert original.canonical_json == original_json

        event_row = session.get(WorkoutEvent, "event-kris-001")
        assert event_row is not None
        assert event_row.effective_revision_number == 2
        effective = get_effective_workout(session, "hwa-kris", "event-kris-001")
        assert effective is not None
        assert effective.revision_number == 2
        assert effective.event.event_id == "event-kris-001"
        assert effective.event.effort.session_rpe == 7
    finally:
        session.close()
        engine.dispose()


def test_wrong_person_cannot_correct_or_read_effective_workout(tmp_path) -> None:
    from hwa.services.workout_evidence import (
        WorkoutEvidenceNotFound,
        correct_workout,
        get_effective_workout,
    )

    engine = create_engine(
        DatabaseSettings(database_url=f"sqlite:///{tmp_path / 'isolation.db'}")
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    try:
        _seed(session)
        _completed(session)
        assert get_effective_workout(session, "hwa-kirsty", "event-kris-001") is None
        with pytest.raises(WorkoutEvidenceNotFound):
            correct_workout(
                session,
                person_id="hwa-kirsty",
                event_id="event-kris-001",
                idempotency_key="correct-wrong-person",
                event=_event(7),
                reason="Not allowed",
                corrected_at=datetime(2026, 10, 1, 18, 0, tzinfo=UTC),
            )
    finally:
        session.close()
        engine.dispose()


def test_persisted_revision_is_immutable(tmp_path) -> None:
    from hwa.db.models.workout import ImmutableWorkoutRevisionError, WorkoutRevision

    engine = create_engine(
        DatabaseSettings(database_url=f"sqlite:///{tmp_path / 'immutable.db'}")
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    try:
        _seed(session)
        _completed(session)
        revision = session.scalar(select(WorkoutRevision))
        assert revision is not None
        revision.correction_reason = "mutated after the fact"
        with pytest.raises(ImmutableWorkoutRevisionError):
            session.commit()
        session.rollback()
    finally:
        session.close()
        engine.dispose()
