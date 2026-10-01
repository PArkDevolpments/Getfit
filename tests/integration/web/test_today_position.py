from datetime import UTC, datetime

from sqlalchemy.orm import Session

from hwa.db.base import Base
from hwa.db.engine import DatabaseSettings, create_engine
from hwa.db.models.identity import Person
from hwa.db.models.programme import ProgrammeDay, ProgrammeDefinition
from hwa.db.models.workout import WorkoutDraft, WorkoutEvent
from hwa.services.today import get_today_view


def _session(tmp_path) -> tuple[Session, object]:
    engine = create_engine(DatabaseSettings(database_url=f"sqlite:///{tmp_path / 'today.db'}"))
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add_all([
        Person(id="hwa-kris", canonical_key="kris", display_name="Kris", presentation_profile="male", active=True),
        Person(id="hwa-kirsty", canonical_key="kirsty", display_name="Kirsty", presentation_profile="female", active=True),
        ProgrammeDefinition(programme_id="home-workout-12m-v1", schema_version=1, title="Home Workout", active=True, seed_checksum="seed"),
    ])
    for day in range(1, 5):
        session.add(ProgrammeDay(id=f"week1-day{day}", programme_id="home-workout-12m-v1", week_number=1, day_number=day, title=f"Day {day}", workout_type="test", block="foundation"))
    session.commit()
    return session, engine


def test_today_starts_at_first_uncompleted_approved_day(tmp_path) -> None:
    session, engine = _session(tmp_path)
    try:
        view = get_today_view(session, "hwa-kris")
        assert (view.week_number, view.day_number, view.primary_action) == (1, 1, "start")

        session.add(WorkoutEvent(event_id="evt-1", person_id="hwa-kris", programme_day_id="week1-day1", effective_revision_number=1, created_at_utc=datetime.now(UTC)))
        session.commit()
        advanced = get_today_view(session, "hwa-kris")
        assert (advanced.week_number, advanced.day_number, advanced.primary_action) == (1, 2, "start")
    finally:
        session.close()
        engine.dispose()


def test_today_resume_draft_takes_precedence(tmp_path) -> None:
    session, engine = _session(tmp_path)
    try:
        session.add(WorkoutDraft(id="draft-1", person_id="hwa-kris", programme_day_id="week1-day3", status="active", version=2, snapshot_json="{}", started_at_utc=datetime.now(UTC), updated_at_utc=datetime.now(UTC)))
        session.commit()
        view = get_today_view(session, "hwa-kris")
        assert (view.week_number, view.day_number, view.primary_action) == (1, 3, "resume")
        assert view.draft_id == "draft-1"
        assert view.draft_version == 2
    finally:
        session.close()
        engine.dispose()


def test_today_is_person_isolated_and_does_not_invent_future_programme(tmp_path) -> None:
    session, engine = _session(tmp_path)
    try:
        for day in range(1, 5):
            session.add(WorkoutEvent(event_id=f"kirsty-{day}", person_id="hwa-kirsty", programme_day_id=f"week1-day{day}", effective_revision_number=1, created_at_utc=datetime.now(UTC)))
        session.commit()
        assert get_today_view(session, "hwa-kris").day_number == 1

        for day in range(1, 5):
            session.add(WorkoutEvent(event_id=f"kris-{day}", person_id="hwa-kris", programme_day_id=f"week1-day{day}", effective_revision_number=1, created_at_utc=datetime.now(UTC)))
        session.commit()
        completed = get_today_view(session, "hwa-kris")
        assert completed.primary_action == "programme_complete"
        assert completed.week_number is None
        assert completed.day_number is None
    finally:
        session.close()
        engine.dispose()
