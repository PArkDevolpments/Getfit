from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from hwa.db.base import Base
from hwa.db.engine import DatabaseSettings, create_engine
from hwa.db.models.identity import ExternalIdentityMapping, Person


def _load_app_factory():
    assert Path("src/hwa/main.py").exists()
    from hwa.auth.principal import StaticPrincipalProvider

    from hwa.main import create_app

    return create_app, StaticPrincipalProvider


def _client(tmp_path, subject_id: str):
    create_app, provider_cls = _load_app_factory()
    engine = create_engine(
        DatabaseSettings(database_url=f"sqlite:///{tmp_path / 'api.db'}")
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    person = Person(
        id="hwa-kris",
        canonical_key="kris",
        display_name="Kris",
        presentation_profile="male",
        active=True,
    )
    session.add(person)
    session.flush()
    mappings = {
        "HOME_ASSISTANT": "ha-user-kris",
        "PEP_SITE": "person_a",
        "HEALTH_PROFILE": "kris",
        "MENU_NUTRITION": "person_1",
    }
    for authority, external_id in mappings.items():
        session.add(
            ExternalIdentityMapping(
                id=f"map-{authority}",
                person_id=person.id,
                authority=authority,
                external_subject_id=external_id,
            )
        )
    session.commit()
    session.close()
    app = create_app(principal_provider=provider_cls(subject_id), engine=engine)
    return TestClient(app), engine


def test_me_returns_server_resolved_person_context(tmp_path) -> None:
    client, engine = _client(tmp_path, "ha-user-kris")
    try:
        response = client.get("/api/v1/me?person_id=hwa-kirsty")
        assert response.status_code == 200
        assert response.json() == {
            "hwa_person_id": "hwa-kris",
            "pep_person_id": "person_a",
            "health_profile_id": "kris",
            "menu_person_id": "person_1",
            "presentation_profile": "male",
            "display_name": "Kris",
        }
    finally:
        engine.dispose()


def test_me_unknown_identity_is_forbidden(tmp_path) -> None:
    client, engine = _client(tmp_path, "ha-user-unknown")
    try:
        response = client.get("/api/v1/me")
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "IDENTITY_NOT_MAPPED"
    finally:
        engine.dispose()
