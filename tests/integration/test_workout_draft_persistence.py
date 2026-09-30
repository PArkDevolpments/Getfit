from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from hwa.db.base import Base
from hwa.db.engine import DatabaseSettings, create_engine
from hwa.db.models.identity import Person
from hwa.db.models.programme import ProgrammeDay, ProgrammeDefinition


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


def test_autosave_updates_same_draft_and_rejects_stale_write(tmp_path) -> None:
    from hwa.db.models.workout import WorkoutDraft
    from hwa.services.workout_drafts import (
        DraftVersionConflict,
        autosave_draft,
        create_draft,
    )

    engine = create_engine(
        DatabaseSettings(database_url=f"sqlite:///{tmp_path / 'draft.db'}")
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    try:
        _seed(session)
        started = datetime(2026, 10, 1, 17, 0, tzinfo=UTC)
        draft = create_draft(
            session,
            person_id="hwa-kris",
            programme_day_id="week1-day1",
            snapshot={"phase": "WORKOUT_READY", "state_data": {}},
            started_at=started,
        )
        assert draft.version == 1

        saved = autosave_draft(
            session,
            draft_id=draft.id,
            person_id="hwa-kris",
            expected_version=1,
            snapshot={
                "phase": "ACTIVE_SET",
                "current_item_kind": "STRENGTH",
                "current_sequence": 1,
                "current_set_number": 1,
                "state_data": {"reps": 10},
            },
            saved_at=datetime(2026, 10, 1, 17, 4, tzinfo=UTC),
        )
        assert saved.id == draft.id
        assert saved.version == 2
        assert session.scalar(select(func.count()).select_from(WorkoutDraft)) == 1

        with pytest.raises(DraftVersionConflict):
            autosave_draft(
                session,
                draft_id=draft.id,
                person_id="hwa-kris",
                expected_version=1,
                snapshot={"phase": "WORKOUT_READY", "state_data": {}},
                saved_at=datetime(2026, 10, 1, 17, 5, tzinfo=UTC),
            )
    finally:
        session.close()
        engine.dispose()


def test_draft_is_person_scoped_and_naive_time_is_rejected(tmp_path) -> None:
    from hwa.services.workout_drafts import create_draft, get_draft

    engine = create_engine(
        DatabaseSettings(database_url=f"sqlite:///{tmp_path / 'isolation.db'}")
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    try:
        _seed(session)
        with pytest.raises(ValueError):
            create_draft(
                session,
                person_id="hwa-kris",
                programme_day_id="week1-day1",
                snapshot={"phase": "WORKOUT_READY", "state_data": {}},
                started_at=datetime(2026, 10, 1, 17, 0),
            )

        draft = create_draft(
            session,
            person_id="hwa-kris",
            programme_day_id="week1-day1",
            snapshot={"phase": "WORKOUT_READY", "state_data": {}},
            started_at=datetime(2026, 10, 1, 17, 0, tzinfo=UTC),
        )
        assert get_draft(session, draft.id, "hwa-kris") is not None
        assert get_draft(session, draft.id, "hwa-kirsty") is None
    finally:
        session.close()
        engine.dispose()
