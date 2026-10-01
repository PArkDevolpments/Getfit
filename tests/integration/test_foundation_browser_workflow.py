from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from hwa.auth.principal import StaticPrincipalProvider
from hwa.db.base import Base
from hwa.db.engine import DatabaseSettings, create_engine
from hwa.db.models.identity import ExternalIdentityMapping, Person
from hwa.db.models.programme import ProgrammeDay, ProgrammeDefinition
from hwa.main import create_app


def _seed(session: Session, *, with_programme: bool = True) -> None:
    people = [
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
    session.add_all(people)
    session.flush()
    mappings = {
        "hwa-kris": {
            "HOME_ASSISTANT": "ha-kris",
            "PEP_SITE": "person_a",
            "HEALTH_PROFILE": "kris",
            "MENU_NUTRITION": "person_1",
        },
        "hwa-kirsty": {
            "HOME_ASSISTANT": "ha-kirsty",
            "PEP_SITE": "person_b",
            "HEALTH_PROFILE": "kirsty",
            "MENU_NUTRITION": "person_2",
        },
    }
    for person_id, subjects in mappings.items():
        for authority, subject in subjects.items():
            session.add(
                ExternalIdentityMapping(
                    id=f"{person_id}-{authority}",
                    person_id=person_id,
                    authority=authority,
                    external_subject_id=subject,
                )
            )
    if with_programme:
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
        for day_number, title, workout_type in [
            (1, "Upper Body + Bike", "upper_body_bike"),
            (2, "Lower Body + Core", "lower_body_core"),
            (3, "Full Body", "full_body"),
            (4, "Cardio + Conditioning", "cardio_conditioning"),
        ]:
            session.add(
                ProgrammeDay(
                    id=f"week1-day{day_number}",
                    programme_id="home-workout-12m-v1",
                    week_number=1,
                    day_number=day_number,
                    title=title,
                    workout_type=workout_type,
                    block="foundation",
                )
            )
    session.commit()


def _client(tmp_path, subject: str, *, with_programme: bool = True):
    engine = create_engine(
        DatabaseSettings(database_url=f"sqlite:///{tmp_path / (subject + '.db')}")
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed(session, with_programme=with_programme)
    return (
        TestClient(create_app(principal_provider=StaticPrincipalProvider(subject), engine=engine)),
        engine,
    )


def test_browser_home_is_person_scoped_and_shows_week1_start(tmp_path) -> None:
    client, engine = _client(tmp_path, "ha-kris")
    try:
        response = client.get("/")
        assert response.status_code == 200
        html = response.text
        assert "Home Workout Assistant" in html
        assert "Kris" in html
        assert "Kirsty" not in html
        assert "Upper Body + Bike" in html
        assert "Lower Body + Core" in html
        assert 'data-primary-action="start"' in html
        assert 'data-programme-day-id="week1-day1"' in html
        assert '"person_id"' not in html
        assert "person_a" not in html
        assert "person_b" not in html
    finally:
        client.close()
        engine.dispose()


def test_browser_home_resumes_server_owned_active_draft(tmp_path) -> None:
    client, engine = _client(tmp_path, "ha-kris")
    try:
        started = client.post(
            "/api/v1/workouts/drafts",
            json={
                "programme_day_id": "week1-day1",
                "snapshot": {"phase": "WORKOUT_READY", "state_data": {}},
                "started_at": datetime(2026, 10, 1, 7, 0, tzinfo=UTC).isoformat(),
            },
        )
        assert started.status_code == 201
        draft = started.json()

        response = client.get("/")
        assert response.status_code == 200
        html = response.text
        assert 'data-primary-action="resume"' in html
        assert draft["draft_id"] in html
        assert f'data-draft-version="{draft["version"]}"' in html
        assert "Start Week 1 Day 1" not in html
    finally:
        client.close()
        engine.dispose()


def test_browser_home_keeps_kirsty_isolated_from_kris(tmp_path) -> None:
    client, engine = _client(tmp_path, "ha-kirsty")
    try:
        response = client.get("/")
        assert response.status_code == 200
        html = response.text
        assert "Kirsty" in html
        assert "Kris" not in html
        assert 'data-primary-action="start"' in html
        assert "person_a" not in html
    finally:
        client.close()
        engine.dispose()


def test_browser_home_degrades_when_programme_is_not_available(tmp_path) -> None:
    client, engine = _client(tmp_path, "ha-kris", with_programme=False)
    try:
        response = client.get("/")
        assert response.status_code == 200
        assert 'data-primary-action="unavailable"' in response.text
        assert "Programme unavailable" in response.text
        assert "Start Week 1 Day 1" not in response.text
    finally:
        client.close()
        engine.dispose()
