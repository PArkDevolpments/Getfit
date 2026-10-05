from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from hwa.auth.principal import StaticPrincipalProvider
from hwa.db.base import Base
from hwa.db.engine import DatabaseSettings, create_engine
from hwa.db.models.identity import ExternalIdentityMapping, Person
from hwa.db.models.programme import (
    ProgrammeDay,
    ProgrammeDefinition,
    ProgrammeStrengthItem,
)
from hwa.main import create_app


def _client(tmp_path) -> tuple[TestClient, object]:
    engine = create_engine(
        DatabaseSettings(database_url=f"sqlite:///{tmp_path / 'library.db'}")
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all(
            [
                Person(
                    id="hwa-kris",
                    canonical_key="kris",
                    display_name="Kris",
                    presentation_profile="male",
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
        for authority, subject in {
            "HOME_ASSISTANT": "ha-kris",
            "PEP_SITE": "person_a",
            "HEALTH_PROFILE": "kris",
            "MENU_NUTRITION": "person_1",
        }.items():
            session.add(
                ExternalIdentityMapping(
                    id=f"kris-{authority}",
                    person_id="hwa-kris",
                    authority=authority,
                    external_subject_id=subject,
                )
            )
        session.add(
            ProgrammeDay(
                id="d1",
                programme_id="home-workout-12m-v1",
                week_number=1,
                day_number=1,
                title="Day 1",
                workout_type="strength",
                block="foundation",
            )
        )
        session.flush()
        session.add_all(
            [
                ProgrammeStrengthItem(
                    id="s1",
                    programme_day_id="d1",
                    sequence=1,
                    exercise_id="goblet-squat",
                    target_type="REPS",
                    sets_target=3,
                    reps_target=8,
                    laterality="BILATERAL",
                    load_mode="SINGLE_IMPLEMENT",
                    load_basis="APPROVED_PROGRAMME",
                ),
                ProgrammeStrengthItem(
                    id="s2",
                    programme_day_id="d1",
                    sequence=2,
                    exercise_id="floor-press",
                    target_type="REPS",
                    sets_target=3,
                    reps_target=8,
                    laterality="BILATERAL",
                    load_mode="PAIR_TOTAL",
                    load_basis="APPROVED_PROGRAMME",
                ),
            ]
        )
        session.commit()
    return (
        TestClient(
            create_app(
                principal_provider=StaticPrincipalProvider("ha-kris"),
                engine=engine,
            )
        ),
        engine,
    )


def test_library_lists_canonical_programme_exercises_without_requiring_media(
    tmp_path,
) -> None:
    client, engine = _client(tmp_path)
    try:
        response = client.get("/library")
        assert response.status_code == 200
        assert "goblet-squat" in response.text
        assert "floor-press" in response.text
        assert 'href="/library/goblet-squat"' in response.text
        assert "Media unavailable" in response.text
        assert 'data-active-nav="more"' in response.text
        assert 'href="/more"' in response.text
        assert 'aria-current="page"' in response.text
    finally:
        client.close()
        engine.dispose()


def test_exercise_detail_is_available_even_when_media_is_missing(tmp_path) -> None:
    client, engine = _client(tmp_path)
    try:
        response = client.get("/library/goblet-squat")
        assert response.status_code == 200
        assert "goblet-squat" in response.text
        assert 'data-media-state="unavailable"' in response.text
        assert "You can still complete this exercise" in response.text
        assert 'data-active-nav="more"' in response.text
    finally:
        client.close()
        engine.dispose()
