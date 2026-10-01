from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

from hwa.db.engine import DatabaseSettings, create_engine
from hwa.db.models.identity import Person
from hwa.db.models.programme import ProgrammeDay, ProgrammeDefinition
from hwa.domain.draft import WorkoutDraftSnapshot
from hwa.services.workout_drafts import create_draft, get_active_draft

_ROOT = Path(__file__).resolve().parents[2]


def _upgrade(database_url: str) -> None:
    config = Config(str(_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


def _seed_draft(database_url: str) -> str:
    engine = create_engine(DatabaseSettings(database_url=database_url))
    try:
        with Session(engine) as session:
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
                ProgrammeDefinition(
                    programme_id="home-workout-12m-v1",
                    schema_version=1,
                    title="Home Workout",
                    active=True,
                    seed_checksum="restart-test",
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

            draft = create_draft(
                session,
                person_id="hwa-kris",
                programme_day_id="week1-day1",
                snapshot=WorkoutDraftSnapshot(
                    phase="ACTIVE_SET",
                    current_item_kind="STRENGTH",
                    current_sequence=2,
                    current_set_number=1,
                    state_data={"reps_entered": 8, "load_kg": 10},
                ),
                started_at=datetime(2026, 10, 1, 17, 0, tzinfo=UTC),
            )
            return draft.id
    finally:
        engine.dispose()


def test_migrations_and_active_draft_survive_process_restart(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'persistent-hwa.db'}"
    _upgrade(database_url)
    draft_id = _seed_draft(database_url)

    _upgrade(database_url)
    restarted_engine = create_engine(DatabaseSettings(database_url=database_url))
    try:
        with Session(restarted_engine) as session:
            draft = get_active_draft(session, "hwa-kris")
            assert draft is not None
            assert draft.id == draft_id
            assert draft.programme_day_id == "week1-day1"
            assert draft.snapshot.phase == "ACTIVE_SET"
            assert draft.snapshot.current_sequence == 2
            assert draft.snapshot.current_set_number == 1
            assert draft.snapshot.state_data == {"reps_entered": 8, "load_kg": 10}
    finally:
        restarted_engine.dispose()
