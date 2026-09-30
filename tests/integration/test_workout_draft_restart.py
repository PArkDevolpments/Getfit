from datetime import UTC, datetime

from sqlalchemy.orm import Session

from hwa.db.base import Base
from hwa.db.engine import DatabaseSettings, create_engine
from hwa.db.models.identity import Person
from hwa.db.models.programme import ProgrammeDay, ProgrammeDefinition


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


def test_active_draft_survives_engine_restart(tmp_path) -> None:
    from hwa.services.workout_drafts import autosave_draft, create_draft, get_active_draft

    url = f"sqlite:///{tmp_path / 'restart.db'}"
    engine = create_engine(DatabaseSettings(database_url=url))
    Base.metadata.create_all(engine)
    session = Session(engine)
    _seed(session)
    draft = create_draft(
        session,
        person_id="hwa-kris",
        programme_day_id="week1-day1",
        snapshot={"phase": "WORKOUT_READY", "state_data": {}},
        started_at=datetime(2026, 10, 1, 17, 0, tzinfo=UTC),
    )
    autosave_draft(
        session,
        draft_id=draft.id,
        person_id="hwa-kris",
        expected_version=1,
        snapshot={
            "phase": "REST_TIMER",
            "current_item_kind": "STRENGTH",
            "current_sequence": 1,
            "current_set_number": 1,
            "state_data": {"rest_seconds_remaining": 47},
        },
        saved_at=datetime(2026, 10, 1, 17, 8, tzinfo=UTC),
    )
    session.close()
    engine.dispose()

    restarted_engine = create_engine(DatabaseSettings(database_url=url))
    restarted_session = Session(restarted_engine)
    try:
        restored = get_active_draft(restarted_session, "hwa-kris")
        assert restored is not None
        assert restored.id == draft.id
        assert restored.version == 2
        assert restored.snapshot.phase.value == "REST_TIMER"
        assert restored.snapshot.state_data["rest_seconds_remaining"] == 47
        assert restored.updated_at == datetime(2026, 10, 1, 17, 8, tzinfo=UTC)
    finally:
        restarted_session.close()
        restarted_engine.dispose()
