from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from hwa.db.base import Base
from hwa.db.engine import DatabaseSettings, create_engine
from hwa.db.models.identity import Person
from hwa.db.models.programme import (
    PersonPrescriptionOverride,
    ProgrammeCardioItem,
    ProgrammeDay,
    ProgrammeDefinition,
    ProgrammeStrengthItem,
)

MANIFEST = Path("programme_seed/home-workout-12m-v1/programme.json")
WEEK = Path("programme_seed/home-workout-12m-v1/week-01.json")


def _session(tmp_path) -> tuple[Session, object]:
    engine = create_engine(
        DatabaseSettings(database_url=f"sqlite:///{tmp_path / 'seed.db'}")
    )
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
        ]
    )
    session.commit()
    return session, engine


def test_week1_import_is_deterministic_and_replay_safe(tmp_path) -> None:
    from hwa.services.programmes import import_week_seed

    session, engine = _session(tmp_path)
    try:
        first = import_week_seed(session, MANIFEST, WEEK)
        assert first.changed is True
        assert first.day_count == 4
        assert first.strength_count > 0
        assert first.cardio_count > 0
        assert first.override_count > 0

        counts_before = {
            "programmes": session.scalar(select(func.count()).select_from(ProgrammeDefinition)),
            "days": session.scalar(select(func.count()).select_from(ProgrammeDay)),
            "strength": session.scalar(select(func.count()).select_from(ProgrammeStrengthItem)),
            "cardio": session.scalar(select(func.count()).select_from(ProgrammeCardioItem)),
            "overrides": session.scalar(
                select(func.count()).select_from(PersonPrescriptionOverride)
            ),
        }

        second = import_week_seed(session, MANIFEST, WEEK)
        assert second.changed is False
        counts_after = {
            "programmes": session.scalar(select(func.count()).select_from(ProgrammeDefinition)),
            "days": session.scalar(select(func.count()).select_from(ProgrammeDay)),
            "strength": session.scalar(select(func.count()).select_from(ProgrammeStrengthItem)),
            "cardio": session.scalar(select(func.count()).select_from(ProgrammeCardioItem)),
            "overrides": session.scalar(
                select(func.count()).select_from(PersonPrescriptionOverride)
            ),
        }
        assert counts_after == counts_before
    finally:
        session.close()
        engine.dispose()


def test_seed_checksum_is_recorded(tmp_path) -> None:
    from hwa.services.programmes import import_week_seed

    session, engine = _session(tmp_path)
    try:
        result = import_week_seed(session, MANIFEST, WEEK)
        programme = session.get(ProgrammeDefinition, "home-workout-12m-v1")
        assert programme is not None
        assert programme.seed_checksum == result.seed_checksum
        assert len(programme.seed_checksum) == 64
    finally:
        session.close()
        engine.dispose()
