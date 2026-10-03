from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from hwa.auth.principal import StaticPrincipalProvider
from hwa.db.base import Base
from hwa.db.engine import DatabaseSettings, create_engine
from hwa.db.models.identity import ExternalIdentityMapping, Person
from hwa.main import create_app


def _client(tmp_path):
    engine = create_engine(
        DatabaseSettings(database_url=f"sqlite:///{tmp_path / 'review-capture.db'}")
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
        for authority, subject in {
            "HOME_ASSISTANT": "ha-kris",
            "PEP_SITE": "person_a",
            "HEALTH_PROFILE": "kris",
            "MENU_NUTRITION": "person_1",
        }.items():
            session.add(
                ExternalIdentityMapping(
                    id=f"review-{authority}",
                    person_id="hwa-kris",
                    authority=authority,
                    external_subject_id=subject,
                )
            )
        session.commit()
    return TestClient(
        create_app(
            principal_provider=StaticPrincipalProvider("ha-kris"),
            engine=engine,
        )
    ), engine


def test_review_capture_is_authenticated_person_scoped_tool(tmp_path) -> None:
    client, engine = _client(tmp_path)
    try:
        response = client.get("/review-capture")
        assert response.status_code == 200
        html = response.text
        assert "UI Review Pack" in html
        assert "Kris" in html
        assert "Run automated specification audit" in html
        assert "Phone" in html
        assert "Tablet" in html
        assert "Desktop" in html
        assert "person_a" not in html
        assert "person_1" not in html
        assert "hwa-kris" not in html
        assert "/static/review-capture.js" in html
        assert "Exercise video — Dumbbell Floor Press · local MP4" in html
        assert "Exercise video — Supported Reverse Lunge · local MP4" in html
        assert "Exercise video — Dumbbell Lateral Raise · local MP4" in html
        assert html.count('"media_tab": "video"') == 3
    finally:
        client.close()
        engine.dispose()


def test_settings_hides_internal_review_tools_from_normal_product_ui(tmp_path) -> None:
    client, engine = _client(tmp_path)
    try:
        response = client.get("/settings")
        assert response.status_code == 200
        assert "UI Review Pack" not in response.text
        assert 'href="/review-capture"' not in response.text

        review = client.get("/review-capture")
        assert review.status_code == 200
        assert "UI Review Pack" in review.text
    finally:
        client.close()
        engine.dispose()
