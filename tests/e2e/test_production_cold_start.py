from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select

import hwa.runtime as runtime
from hwa.auth.ha_ingress import HomeAssistantIngressPrincipalProvider
from hwa.db.engine import DatabaseSettings, create_engine
from hwa.db.models.identity import ExternalIdentityMapping
from hwa.db.models.programme import PersonProgrammeAssignment, ProgrammeDay

ROOT = Path(__file__).resolve().parents[2]
SEED_ROOT = ROOT / "programme_seed"
PROGRAMME_ID = "home-workout-12m-v1"


def _migrate_empty_database(db_path: Path) -> None:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    command.upgrade(config, "head")


def _wire_runtime_to_database(monkeypatch, db_path: Path) -> list[Engine]:
    engines: list[Engine] = []

    def _factory() -> Engine:
        engine = create_engine(
            DatabaseSettings(database_url=f"sqlite:///{db_path}")
        )
        engines.append(engine)
        return engine

    monkeypatch.setattr(runtime, "create_engine", _factory)
    monkeypatch.setenv("HWA_PROGRAMME_SEED_ROOT", str(SEED_ROOT))
    return engines


def _trusted_client(app) -> TestClient:
    app.state.principal_provider = HomeAssistantIngressPrincipalProvider(
        trusted_hosts={"testclient"}
    )
    return TestClient(app)


def _headers(subject_id: str) -> dict[str, str]:
    return {"X-Remote-User-Id": subject_id}


def test_cold_start_bootstraps_kris_and_resumes_same_draft_after_restart(
    monkeypatch,
    tmp_path,
) -> None:
    db_path = tmp_path / "production-cold-start.db"
    _migrate_empty_database(db_path)
    engines = _wire_runtime_to_database(monkeypatch, db_path)
    monkeypatch.setenv("HWA_KRIS_HA_USER_ID", "real-ha-user-id")
    monkeypatch.setenv("HWA_KIRSTY_HA_USER_ID", "")

    first_app = runtime.build_production_app()
    first_client = _trusted_client(first_app)
    try:
        today = first_client.get("/", headers=_headers("real-ha-user-id"))
        assert today.status_code == 200
        assert "Kris" in today.text
        assert "Kirsty" not in today.text
        assert "Upper Body + Bike" in today.text
        assert 'data-primary-action="start"' in today.text

        with first_app.state.session_factory() as session:
            day = session.scalar(
                select(ProgrammeDay)
                .where(
                    ProgrammeDay.programme_id == PROGRAMME_ID,
                    ProgrammeDay.week_number == 1,
                    ProgrammeDay.day_number == 1,
                )
                .limit(1)
            )
            assert day is not None

        started = first_client.post(
            "/api/v1/workouts/drafts",
            headers=_headers("real-ha-user-id"),
            json={
                "programme_day_id": day.id,
                "snapshot": {"phase": "WORKOUT_READY", "state_data": {}},
                "started_at": datetime(2026, 10, 1, 18, 50, tzinfo=UTC).isoformat(),
            },
        )
        assert started.status_code == 201
        draft = started.json()
    finally:
        first_client.close()
        engines[0].dispose()

    second_app = runtime.build_production_app()
    second_client = _trusted_client(second_app)
    try:
        resumed = second_client.get("/", headers=_headers("real-ha-user-id"))
        assert resumed.status_code == 200
        assert 'data-primary-action="resume"' in resumed.text
        assert draft["draft_id"] in resumed.text
        assert f'data-draft-version="{draft["version"]}"' in resumed.text
        assert "Kirsty" not in resumed.text

        with second_app.state.session_factory() as session:
            assignment = session.scalar(
                select(PersonProgrammeAssignment).where(
                    PersonProgrammeAssignment.person_id == "hwa-kris",
                    PersonProgrammeAssignment.programme_id == PROGRAMME_ID,
                    PersonProgrammeAssignment.status == "ACTIVE",
                )
            )
            assert assignment is not None
            kirsty_ha = session.scalar(
                select(ExternalIdentityMapping).where(
                    ExternalIdentityMapping.person_id == "hwa-kirsty",
                    ExternalIdentityMapping.authority == "HOME_ASSISTANT",
                )
            )
            assert kirsty_ha is None
    finally:
        second_client.close()
        engines[1].dispose()


def test_unmapped_setup_becomes_kris_today_after_explicit_configuration(
    monkeypatch,
    tmp_path,
) -> None:
    db_path = tmp_path / "setup-to-config.db"
    _migrate_empty_database(db_path)
    engines = _wire_runtime_to_database(monkeypatch, db_path)
    monkeypatch.setenv("HWA_KRIS_HA_USER_ID", "")
    monkeypatch.setenv("HWA_KIRSTY_HA_USER_ID", "")

    unmapped_app = runtime.build_production_app()
    unmapped_client = _trusted_client(unmapped_app)
    try:
        setup = unmapped_client.get("/", headers=_headers("new-real-ha-user-id"))
        assert setup.status_code == 403
        assert setup.headers["content-type"].startswith("text/html")
        assert "Getfit setup required" in setup.text
        assert "new-real-ha-user-id" in setup.text
        assert "Kris" not in setup.text
        assert "Kirsty" not in setup.text
    finally:
        unmapped_client.close()
        engines[0].dispose()

    monkeypatch.setenv("HWA_KRIS_HA_USER_ID", "new-real-ha-user-id")
    configured_app = runtime.build_production_app()
    configured_client = _trusted_client(configured_app)
    try:
        today = configured_client.get("/", headers=_headers("new-real-ha-user-id"))
        assert today.status_code == 200
        assert "Kris" in today.text
        assert "Kirsty" not in today.text
        assert "Upper Body + Bike" in today.text
        assert 'data-primary-action="start"' in today.text

        with configured_app.state.session_factory() as session:
            mapping = session.scalar(
                select(ExternalIdentityMapping).where(
                    ExternalIdentityMapping.person_id == "hwa-kris",
                    ExternalIdentityMapping.authority == "HOME_ASSISTANT",
                )
            )
            assert mapping is not None
            assert mapping.external_subject_id == "new-real-ha-user-id"
            assignment = session.scalar(
                select(PersonProgrammeAssignment).where(
                    PersonProgrammeAssignment.person_id == "hwa-kris",
                    PersonProgrammeAssignment.programme_id == PROGRAMME_ID,
                    PersonProgrammeAssignment.status == "ACTIVE",
                )
            )
            assert assignment is not None
    finally:
        configured_client.close()
        engines[1].dispose()
