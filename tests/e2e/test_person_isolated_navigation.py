from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from hwa.auth.principal import StaticPrincipalProvider
from hwa.db.base import Base
from hwa.db.engine import DatabaseSettings, create_engine
from hwa.db.models.identity import ExternalIdentityMapping, Person
from hwa.main import create_app


def _client(tmp_path, *, subject: str) -> tuple[TestClient, object]:
    database_url = f"sqlite:///{tmp_path / (subject + '.db')}"
    engine = create_engine(DatabaseSettings(database_url=database_url))
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        people = (
            (
                "hwa-kris",
                "kris",
                "Kris",
                "male",
                "ha-kris",
                "person_a",
                "kris",
                "person_1",
            ),
            (
                "hwa-kirsty",
                "kirsty",
                "Kirsty",
                "female",
                "ha-kirsty",
                "person_b",
                "kirsty",
                "person_2",
            ),
        )
        for person_id, key, name, profile, ha, pep, health, menu in people:
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
            for authority, external_id in (
                ("HOME_ASSISTANT", ha),
                ("PEP_SITE", pep),
                ("HEALTH_PROFILE", health),
                ("MENU_NUTRITION", menu),
            ):
                session.add(
                    ExternalIdentityMapping(
                        id=f"{person_id}-{authority}",
                        person_id=person_id,
                        authority=authority,
                        external_subject_id=external_id,
                    )
                )
        session.commit()
    app = create_app(
        principal_provider=StaticPrincipalProvider(subject),
        engine=engine,
    )
    return TestClient(app), engine


def test_all_product_surfaces_are_person_scoped(tmp_path) -> None:
    client, engine = _client(tmp_path, subject="ha-kris")
    surfaces = (
        ("/", "today"),
        ("/plan", "plan"),
        ("/workout", "workout"),
        ("/progress", "progress"),
        ("/more", "more"),
        ("/library", "workout"),
        ("/settings", "more"),
    )
    try:
        for path, active in surfaces:
            response = client.get(path)
            assert response.status_code == 200, path
            assert "Kris" in response.text
            assert "Kirsty" not in response.text
            assert f'data-active-nav="{active}"' in response.text
            for href in ("/", "/plan", "/workout", "/progress", "/more"):
                assert f'href="{href}"' in response.text
            assert "person_a" not in response.text
            assert "person_b" not in response.text
    finally:
        client.close()
        engine.dispose()


def test_kirsty_navigation_never_falls_back_to_kris(tmp_path) -> None:
    client, engine = _client(tmp_path, subject="ha-kirsty")
    try:
        for path in ("/", "/plan", "/workout", "/progress", "/more", "/library", "/settings"):
            response = client.get(path)
            assert response.status_code == 200
            assert "Kirsty" in response.text
            assert "Kris" not in response.text
            assert "person_a" not in response.text
    finally:
        client.close()
        engine.dispose()


def test_browser_identity_selector_spoof_fails_closed(tmp_path) -> None:
    client, engine = _client(tmp_path, subject="ha-kris")
    selectors = (
        "person_id",
        "hwa_person_id",
        "pep_person_id",
        "health_profile_id",
        "menu_person_id",
    )
    try:
        for selector in selectors:
            response = client.get(f"/progress?{selector}=hwa-kirsty")
            assert response.status_code == 400
            assert response.json() == {"detail": "IDENTITY_SELECTOR_NOT_ALLOWED"}
            assert "Kirsty" not in response.text
    finally:
        client.close()
        engine.dispose()
