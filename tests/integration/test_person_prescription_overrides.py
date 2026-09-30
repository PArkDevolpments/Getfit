from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from hwa.db.base import Base
from hwa.db.engine import DatabaseSettings, create_engine
from hwa.db.models.identity import Person
from hwa.db.models.programme import (
    PersonPrescriptionOverride,
    ProgrammeDay,
    ProgrammeStrengthItem,
)

MANIFEST = Path("programme_seed/home-workout-12m-v1/programme.json")
WEEK = Path("programme_seed/home-workout-12m-v1/week-01.json")


def test_kris_loads_import_as_person_specific_overrides_only(tmp_path) -> None:
    from hwa.services.programmes import import_week_seed

    engine = create_engine(
        DatabaseSettings(database_url=f"sqlite:///{tmp_path / 'overrides.db'}")
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    try:
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
        import_week_seed(session, MANIFEST, WEEK)

        rows = session.execute(
            select(
                Person.canonical_key,
                ProgrammeDay.day_number,
                ProgrammeStrengthItem.exercise_id,
                PersonPrescriptionOverride.load_value,
                PersonPrescriptionOverride.load_mode,
            )
            .join(
                PersonPrescriptionOverride,
                PersonPrescriptionOverride.person_id == Person.id,
            )
            .join(
                ProgrammeStrengthItem,
                ProgrammeStrengthItem.id
                == PersonPrescriptionOverride.programme_strength_item_id,
            )
            .join(
                ProgrammeDay,
                ProgrammeDay.id == ProgrammeStrengthItem.programme_day_id,
            )
        ).all()

        assert rows
        assert {row.canonical_key for row in rows} == {"kris"}
        values = {
            (row.day_number, row.exercise_id): (float(row.load_value), row.load_mode)
            for row in rows
        }
        assert values[(1, "dumbbell_floor_press")] == (6.0, "EACH_HAND")
        assert values[(2, "goblet_squat")] == (10.0, "SINGLE_IMPLEMENT")
        assert values[(2, "dumbbell_romanian_deadlift")] == (8.0, "EACH_HAND")
        assert values[(3, "dumbbell_lateral_raise")] == (3.0, "EACH_HAND")
    finally:
        session.close()
        engine.dispose()
