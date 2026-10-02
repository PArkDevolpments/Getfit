from pathlib import Path

from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from hwa.auth.principal import StaticPrincipalProvider
from hwa.db.base import Base
from hwa.db.engine import DatabaseSettings, create_engine
from hwa.db.models.identity import ExternalIdentityMapping, Person
from hwa.db.models.programme import ProgrammeDay, ProgrammeDefinition
from hwa.main import create_app
from hwa.web.urls import ingress_prefix, ingress_url

ROOT = Path(__file__).resolve().parents[2]


def _request(path: str = "/", ingress_path: str | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if ingress_path is not None:
        headers.append((b"x-ingress-path", ingress_path.encode("ascii")))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "headers": headers,
        "client": ("127.0.0.1", 1234),
        "server": ("testserver", 80),
    }
    return Request(scope)


def _client(tmp_path) -> tuple[TestClient, object]:
    engine = create_engine(
        DatabaseSettings(database_url=f"sqlite:///{tmp_path / 'ingress-ui.db'}")
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
                    id=f"ingress-{authority}",
                    person_id="hwa-kris",
                    authority=authority,
                    external_subject_id=subject,
                )
            )
        session.add(
            ProgrammeDefinition(
                programme_id="home-workout-12m-v1",
                schema_version=1,
                title="Home Workout",
                active=True,
                seed_checksum="seed",
            )
        )
        session.flush()
        session.add(
            ProgrammeDay(
                id="week1-day1",
                programme_id="home-workout-12m-v1",
                week_number=1,
                day_number=1,
                title="Upper Body + Bike",
                workout_type="upper_body_bike",
                block="foundation",
            )
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


def test_ingress_url_prefixes_assets_routes_and_api_paths() -> None:
    request = _request(ingress_path="/api/hassio_ingress/abcDEF_123-token")

    assert ingress_prefix(request) == "/api/hassio_ingress/abcDEF_123-token"
    assert ingress_url(request, "/static/app.css") == (
        "/api/hassio_ingress/abcDEF_123-token/static/app.css"
    )
    assert ingress_url(request, "/workout") == "/api/hassio_ingress/abcDEF_123-token/workout"
    assert ingress_url(request, "/api/v1/workouts/drafts") == (
        "/api/hassio_ingress/abcDEF_123-token/api/v1/workouts/drafts"
    )


def test_direct_requests_keep_root_relative_application_paths() -> None:
    request = _request()

    assert ingress_prefix(request) == ""
    assert ingress_url(request, "/static/app.css") == "/static/app.css"
    assert ingress_url(request, "/") == "/"


def test_ingress_prefix_rejects_non_supervisor_path_shapes() -> None:
    assert ingress_prefix(_request(ingress_path="//evil.example")) == ""
    assert ingress_prefix(_request(ingress_path="javascript:alert(1)")) == ""
    assert ingress_prefix(_request(ingress_path="/api/hassio_ingress/token/extra")) == ""


def test_rendered_product_paths_follow_supervisor_ingress_prefix(tmp_path) -> None:
    client, engine = _client(tmp_path)
    prefix = "/api/hassio_ingress/abcDEF_123-token"
    try:
        today = client.get("/", headers={"X-Ingress-Path": prefix})
        assert today.status_code == 200
        assert f'href="{prefix}/static/app.css"' in today.text
        assert f'href="{prefix}/workout"' in today.text
        assert f"fetch(\'{prefix}/api/v1/workouts/drafts\')" in today.text

        workout = client.get("/workout", headers={"X-Ingress-Path": prefix})
        assert workout.status_code == 200
        assert f'href="{prefix}/static/workout.css"' in workout.text

        static_css = client.get("/static/app.css")
        assert static_css.status_code == 200
        assert "--colour-accent:" in static_css.text
    finally:
        client.close()
        engine.dispose()


def test_templates_do_not_hardcode_root_absolute_assets_or_navigation() -> None:
    template_dir = ROOT / "src/hwa/web/templates"
    templates = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(template_dir.glob("*.html"))
    )

    assert 'href="/static/' not in templates
    assert 'src="/static/' not in templates
    assert "fetch('/api/" not in templates
    assert 'href="/library' not in templates
