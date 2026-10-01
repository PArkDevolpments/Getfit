from fastapi.testclient import TestClient

from hwa.auth.principal import StaticPrincipalProvider
from hwa.db.base import Base
from hwa.db.engine import DatabaseSettings, create_engine
from hwa.main import create_app


def _client(tmp_path, subject_id: str):
    engine = create_engine(
        DatabaseSettings(database_url=f"sqlite:///{tmp_path / 'setup-required.db'}")
    )
    Base.metadata.create_all(engine)
    app = create_app(
        principal_provider=StaticPrincipalProvider(subject_id),
        engine=engine,
    )
    return TestClient(app), engine


def _assert_safe_setup_page(response, subject_id: str) -> None:
    assert response.status_code == 403
    assert response.headers["content-type"].startswith("text/html")
    html = response.text
    assert "Getfit setup required" in html
    assert subject_id in html
    assert "kris_ha_user_id" in html
    assert "kirsty_ha_user_id" in html
    assert "restart Getfit" in html
    assert "person_a" not in html
    assert "person_b" not in html
    assert "person_1" not in html
    assert "person_2" not in html
    assert "hwa-kris" not in html
    assert "hwa-kirsty" not in html
    assert "token" not in html.lower()


def test_unmapped_authenticated_user_gets_setup_page_on_today(tmp_path) -> None:
    client, engine = _client(tmp_path, "real-ha-user-id")
    try:
        response = client.get("/")
        _assert_safe_setup_page(response, "real-ha-user-id")
    finally:
        client.close()
        engine.dispose()


def test_unmapped_authenticated_user_gets_setup_page_on_settings(tmp_path) -> None:
    client, engine = _client(tmp_path, "second-ha-user-id")
    try:
        response = client.get("/settings")
        _assert_safe_setup_page(response, "second-ha-user-id")
        assert "real-ha-user-id" not in response.text
    finally:
        client.close()
        engine.dispose()
