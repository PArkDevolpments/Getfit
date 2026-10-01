from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from hwa.auth.principal import StaticPrincipalProvider
from hwa.db.base import Base
from hwa.db.engine import DatabaseSettings, create_engine
from hwa.db.models.identity import ExternalIdentityMapping, Person
from hwa.db.models.programme import ProgrammeDay
from hwa.main import create_app
from hwa.services.programmes import import_week_seed

PROGRAMME_MANIFEST = Path("programme_seed/home-workout-12m-v1/programme.json")
WEEK_ONE = Path("programme_seed/home-workout-12m-v1/week-01.json")


def _seed(session: Session) -> str:
    for person_id, key, name, profile in (
        ("hwa-kris", "kris", "Kris", "male"),
        ("hwa-kirsty", "kirsty", "Kirsty", "female"),
    ):
        session.add(
            Person(
                id=person_id,
                canonical_key=key,
                display_name=name,
                presentation_profile=profile,
                active=True,
            )
        )
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
    for person_id, values in mappings.items():
        for authority, subject in values.items():
            session.add(
                ExternalIdentityMapping(
                    id=f"{person_id}-{authority}",
                    person_id=person_id,
                    authority=authority,
                    external_subject_id=subject,
                )
            )
    session.commit()
    import_week_seed(session, PROGRAMME_MANIFEST, WEEK_ONE)
    day = session.scalar(
        select(ProgrammeDay).where(
            ProgrammeDay.programme_id == "home-workout-12m-v1",
            ProgrammeDay.week_number == 1,
            ProgrammeDay.day_number == 1,
        )
    )
    assert day is not None
    return day.id


def test_kirsty_never_inherits_kris_draft_identity_or_page_state(tmp_path) -> None:
    engine = create_engine(DatabaseSettings(database_url=f"sqlite:///{tmp_path / 'people.db'}"))
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        day_id = _seed(session)

    kris = TestClient(
        create_app(principal_provider=StaticPrincipalProvider("ha-kris"), engine=engine)
    )
    kirsty = TestClient(
        create_app(principal_provider=StaticPrincipalProvider("ha-kirsty"), engine=engine)
    )
    try:
        draft = kris.post(
            "/api/v1/workouts/drafts",
            json={
                "programme_day_id": day_id,
                "snapshot": {
                    "phase": "ACTIVE_SET",
                    "state_data": {"private_marker": "KRIS_ONLY"},
                },
                "started_at": "2026-10-01T09:00:00Z",
            },
        )
        assert draft.status_code == 201
        draft_id = draft.json()["draft_id"]

        kris_today = kris.get("/")
        assert 'data-primary-action="resume"' in kris_today.text
        assert draft_id in kris_today.text

        kirsty_today = kirsty.get("/")
        assert kirsty_today.status_code == 200
        assert "Kirsty" in kirsty_today.text
        assert "Kris" not in kirsty_today.text
        assert draft_id not in kirsty_today.text
        assert "KRIS_ONLY" not in kirsty_today.text
        assert 'data-primary-action="start"' in kirsty_today.text

        assert kirsty.get("/api/v1/workouts/drafts/active").status_code == 404
        spoof = kirsty.get("/?person_id=hwa-kris")
        assert spoof.status_code == 400
        assert spoof.json()["detail"] == "IDENTITY_SELECTOR_NOT_ALLOWED"

        settings = kirsty.get("/settings")
        assert settings.status_code == 200
        assert "Kirsty" in settings.text
        assert "Kris" not in settings.text
        assert "person_a" not in settings.text
        assert "person_b" not in settings.text
    finally:
        kris.close()
        kirsty.close()
        engine.dispose()
