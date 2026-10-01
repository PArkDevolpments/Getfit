from pathlib import Path

import yaml
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from hwa.auth.ha_ingress import HomeAssistantIngressPrincipalProvider
from hwa.db.base import Base
from hwa.db.engine import DatabaseSettings, create_engine
from hwa.db.models.identity import ExternalIdentityMapping, Person
from hwa.main import create_app

_ROOT = Path(__file__).resolve().parents[2]


def _seed_identity(session: Session) -> None:
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
                id=f"hwa-kris-{authority}",
                person_id="hwa-kris",
                authority=authority,
                external_subject_id=subject,
            )
        )
    session.commit()


def _engine(tmp_path):
    engine = create_engine(DatabaseSettings(database_url=f"sqlite:///{tmp_path / 'ingress.db'}"))
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed_identity(session)
    return engine


def test_home_assistant_app_package_declares_ingress_and_persistent_runtime() -> None:
    config = yaml.safe_load((_ROOT / "config.yaml").read_text(encoding="utf-8"))
    dockerfile = (_ROOT / "Dockerfile").read_text(encoding="utf-8")
    run_script = (_ROOT / "run.sh").read_text(encoding="utf-8")
    alembic = (_ROOT / "alembic.ini").read_text(encoding="utf-8")

    assert config["name"] == "Getfit"
    assert config["slug"] == "getfit"
    assert config["ingress"] is True
    assert config["ingress_port"] == 8099
    assert config["init"] is False
    assert set(config["arch"]) == {"amd64", "aarch64"}

    assert "FROM ghcr.io/home-assistant/base-python:3.12-alpine3.24" in dockerfile
    assert "ARG BUILD_FROM" not in dockerfile
    assert "COPY migrations /app/migrations" in dockerfile
    assert "COPY src /app/src" in dockerfile

    assert "cd /data" in run_script
    assert "alembic -c /app/alembic.ini upgrade head" in run_script
    assert "uvicorn hwa.main:app" in run_script
    assert "--port 8099" in run_script
    assert "%(here)s/migrations" in alembic


def test_direct_spoofed_ingress_header_remains_rejected(tmp_path) -> None:
    engine = _engine(tmp_path)
    client = TestClient(create_app(engine=engine))
    try:
        response = client.get(
            "/api/v1/me",
            headers={"X-Remote-User-Id": "ha-kris"},
        )
        assert response.status_code == 401
        assert response.json()["detail"]["code"] == "UNAUTHENTICATED_INGRESS"
    finally:
        client.close()
        engine.dispose()


def test_trusted_supervisor_ingress_resolves_only_mapped_person(tmp_path) -> None:
    engine = _engine(tmp_path)
    provider = HomeAssistantIngressPrincipalProvider(trusted_hosts={"testclient"})
    client = TestClient(create_app(principal_provider=provider, engine=engine))
    try:
        response = client.get(
            "/api/v1/me",
            headers={"X-Remote-User-Id": "ha-kris"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["hwa_person_id"] == "hwa-kris"
        assert payload["display_name"] == "Kris"
        assert payload["pep_person_id"] == "person_a"
    finally:
        client.close()
        engine.dispose()
