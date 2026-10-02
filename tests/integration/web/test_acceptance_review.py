from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from hwa.auth.principal import StaticPrincipalProvider
from hwa.db.base import Base
from hwa.db.engine import DatabaseSettings, create_engine
from hwa.db.models.identity import ExternalIdentityMapping, Person
from hwa.main import create_app


def _client(tmp_path):
    engine = create_engine(
        DatabaseSettings(database_url=f"sqlite:///{tmp_path / 'acceptance-review.db'}")
    )
    Base.metadata.create_all(engine)
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
            ExternalIdentityMapping(
                id="acceptance-ha",
                person_id="hwa-kris",
                authority="HOME_ASSISTANT",
                external_subject_id="ha-kris",
            )
        )
        session.commit()

    client = TestClient(
        create_app(
            principal_provider=StaticPrincipalProvider("ha-kris"),
            engine=engine,
        )
    )
    return client, engine


def test_acceptance_review_is_person_scoped_and_versioned(tmp_path) -> None:
    client, engine = _client(tmp_path)
    try:
        response = client.get("/review-spec")
        assert response.status_code == 200
        html = response.text
        assert "Specification &amp; Acceptance" in html or "Specification & Acceptance" in html
        assert "Kris" in html
        assert "2026-10-02-v1" in html
        assert "GATE-1-TODAY" in html
        assert "GATE-2-STRENGTH" in html
        assert "TODAY-01" in html
        assert "STRENGTH-01" in html
        assert "PASS" in html
        assert "FAIL" in html
        assert "BLOCKED" in html
        assert "No active workout draft exists" in html
        assert "hwa-kris" not in html
        assert "ha-kris" not in html
    finally:
        client.close()
        engine.dispose()


def test_review_capture_includes_acceptance_payload_hooks(tmp_path) -> None:
    client, engine = _client(tmp_path)
    try:
        response = client.get("/review-capture")
        assert response.status_code == 200
        html = response.text
        assert 'id="acceptance-specification"' in html
        assert 'id="acceptance-storage-key"' in html
        assert "2026-10-02-v1" in html
        assert "Specification &amp; Acceptance" in html or "Specification & Acceptance" in html
    finally:
        client.close()
        engine.dispose()
