import asyncio
import base64
import importlib.util
import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select

import hwa.runtime as runtime
from hwa.auth.ha_ingress import HomeAssistantIngressPrincipalProvider
from hwa.db.engine import DatabaseSettings, create_engine
from hwa.db.models.identity import ExternalIdentityMapping
from hwa.db.models.programme import PersonProgrammeAssignment, ProgrammeDay
from hwa.domain.identity import PersonContext
from hwa.integrations.pep.ha_health_service import HaHealthServiceClient

ROOT = Path(__file__).resolve().parents[2]
SEED_ROOT = ROOT / "programme_seed"
PROGRAMME_ID = "home-workout-12m-v1"
HEALTH_PERSON = PersonContext("hwa-kris", "person_a", "kris", "person_1", "male", "Kris")

_spec = importlib.util.spec_from_file_location(
    "cold_start_health_fixtures", ROOT / "tests/fixtures/pep_health_service_responses.py"
)
assert _spec is not None and _spec.loader is not None
_fixtures = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fixtures)


def _configure_health(monkeypatch, tmp_path, state):
    key = Ed25519PrivateKey.generate()
    path = tmp_path / "synthetic-signing.key"
    encoded = base64.urlsafe_b64encode(key.private_bytes_raw()).decode().rstrip("=")
    path.write_text(encoded if state != "invalid-key" else "private-invalid-sentinel")
    path.chmod(0o600)
    monkeypatch.setenv("HWA_PEP_HEALTH_SIGNING_KEY_FILE", str(path))
    monkeypatch.setenv("HWA_PEP_HEALTH_SIGNING_KID", "synthetic-kid")
    monkeypatch.setenv("HWA_KRIS_HA_USER_ID", "synthetic-ha-user")
    monkeypatch.setenv("HWA_KIRSTY_HA_USER_ID", "")
    if state == "default-off":
        monkeypatch.delenv("HWA_PEP_HEALTH_ENABLED", raising=False)
    else:
        monkeypatch.setenv("HWA_PEP_HEALTH_ENABLED", "true")
    if state == "missing-token":
        monkeypatch.delenv("SUPERVISOR_TOKEN", raising=False)
    else:
        monkeypatch.setenv("SUPERVISOR_TOKEN", "synthetic-supervisor-secret")
    assertions = []

    class Socket:
        def __init__(self):
            body = _fixtures.ready_projection(person_id="person_a", health_profile_id="kris")
            self.frames = iter([
                {"type": "auth_required", "ha_version": "synthetic"},
                {"type": "auth_ok", "ha_version": "synthetic"},
                _fixtures.websocket_result(_fixtures.service_response(body)),
            ])

        async def recv(self):
            return json.dumps(next(self.frames))

        async def send(self, frame):
            message = json.loads(frame)
            if message["type"] == "auth":
                assert message == {"type": "auth", "access_token": "synthetic-supervisor-secret"}
                assert "SUPERVISOR_TOKEN" not in runtime.os.environ
                return
            assert set(message) == {
                "id", "type", "domain", "service", "service_data", "return_response"
            }
            assert message["domain"] == "peptide_site"
            assert message["service"] == "get_health_context"
            assert message["return_response"] is True
            assert set(message["service_data"]) == {"assertion"}
            assertion = message["service_data"]["assertion"]
            header, payload, signature = assertion.split(".")
            key.public_key().verify(
                base64.urlsafe_b64decode(signature + "=="), f"{header}.{payload}".encode()
            )
            claims = json.loads(base64.urlsafe_b64decode(payload + "=="))
            assert claims["sub"] == "synthetic-ha-user"
            assert claims["kid"] == "synthetic-kid"
            assert claims["exp"] - claims["iat"] == 30
            assertions.append(assertion)

    @asynccontextmanager
    async def connector(endpoint, **kwargs):
        assert endpoint == "ws://supervisor/core/websocket"
        assert kwargs["close_timeout"] == 5.0
        assert kwargs["proxy"] is None
        assert state == "valid", "disabled or invalid Health must never connect"
        yield Socket()

    def client_factory(**kwargs):
        assert kwargs["timeout_seconds"] == 5.0
        return HaHealthServiceClient(connector=connector, **kwargs)

    monkeypatch.setattr(runtime, "HaHealthServiceClient", client_factory, raising=False)
    return encoded, assertions


@pytest.mark.parametrize(
    ("state", "reason"),
    [
        ("default-off", "GETFIT_PEP_HEALTH_DISABLED"),
        ("valid", "OK"),
        ("missing-token", "PEP_HEALTH_CONFIGURATION_INVALID"),
        ("invalid-key", "PEP_HEALTH_CONFIGURATION_INVALID"),
    ],
)
def test_production_health_cold_start_keeps_workouts_usable(
    monkeypatch, tmp_path, caplog, state, reason,
) -> None:
    path = tmp_path / "cold-start-health.db"
    _migrate_empty_database(path)
    engines = _wire_runtime_to_database(monkeypatch, path)
    encoded, assertions = _configure_health(monkeypatch, tmp_path, state)
    app = runtime.build_production_app()
    try:
        assert app.state.pep_health_reader is not None
        context = asyncio.run(app.state.pep_health_reader.read(
            ha_user_id="synthetic-ha-user", person=HEALTH_PERSON,
        ))
        assert context.reason == reason
        assert context.status == ("READY" if state == "valid" else "UNAVAILABLE")
        with _trusted_client(app) as client:
            for route in ("/", "/workout", "/healthz"):
                response = client.get(route, headers=_headers("synthetic-ha-user"))
                assert response.status_code == 200
                assert encoded not in response.text
                assert "synthetic-supervisor-secret" not in response.text
                assert "synthetic-ha-user" not in response.text
                assert "ws://supervisor" not in response.text
            with app.state.session_factory() as session:
                day = session.scalar(select(ProgrammeDay).where(
                    ProgrammeDay.programme_id == PROGRAMME_ID,
                    ProgrammeDay.week_number == 1, ProgrammeDay.day_number == 1,
                ))
            assert day is not None
            started = client.post(
                "/api/v1/workouts/drafts", headers=_headers("synthetic-ha-user"),
                json={
                    "programme_day_id": day.id,
                    "snapshot": {"phase": "WORKOUT_READY", "state_data": {}},
                    "started_at": "2026-10-01T18:50:00Z",
                },
            )
            assert started.status_code == 201
            assert 'data-primary-action="resume"' in client.get(
                "/", headers=_headers("synthetic-ha-user")
            ).text
        public = repr(app.state._state) + caplog.text
        assert encoded not in public
        assert "synthetic-supervisor-secret" not in public
        assert all(assertion not in public for assertion in assertions)
        if state != "default-off":
            assert "SUPERVISOR_TOKEN" not in runtime.os.environ
    finally:
        engines[0].dispose()


@pytest.mark.parametrize("restart_state", ["disabled", "missing-token", "valid"])
def test_health_restart_never_reuses_projection_or_assertion(
    monkeypatch, tmp_path, restart_state,
) -> None:
    path = tmp_path / "restart-health.db"
    _migrate_empty_database(path)
    engines = _wire_runtime_to_database(monkeypatch, path)
    _, assertions = _configure_health(monkeypatch, tmp_path, "valid")
    first = runtime.build_production_app()
    assert first.state.pep_health_reader is not None
    context = asyncio.run(first.state.pep_health_reader.read(
        ha_user_id="synthetic-ha-user", person=HEALTH_PERSON,
    ))
    assert context.status == "READY"
    assert context.body["body_mass"].value == 80.0
    engines[0].dispose()
    if restart_state == "disabled":
        monkeypatch.setenv("HWA_PEP_HEALTH_ENABLED", "false")
    elif restart_state == "valid":
        monkeypatch.setenv("SUPERVISOR_TOKEN", "synthetic-supervisor-secret")
    second = runtime.build_production_app()
    try:
        restarted = asyncio.run(second.state.pep_health_reader.read(
            ha_user_id="synthetic-ha-user", person=HEALTH_PERSON,
        ))
        if restart_state == "valid":
            assert restarted.status == "READY"
            assert len(assertions) == len(set(assertions)) == 2
            assert restarted is not context
        else:
            assert restarted.status == "UNAVAILABLE"
            assert restarted.reason == (
                "GETFIT_PEP_HEALTH_DISABLED" if restart_state == "disabled"
                else "PEP_HEALTH_CONFIGURATION_INVALID"
            )
            assert restarted.body == {}
            assert restarted.exported_at is None
            assert restarted.progress is None
        assert second.state.pep_health_reader is not first.state.pep_health_reader
        with _trusted_client(second) as client:
            assert client.get("/", headers=_headers("synthetic-ha-user")).status_code == 200
    finally:
        engines[1].dispose()


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
        assert "new-real-ha-user-id" not in setup.text
        assert "administrator" in setup.text
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
