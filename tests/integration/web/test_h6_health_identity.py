"""Trusted request identity reaches real H6 signing without browser selectors."""

import base64
import importlib.util
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from hwa.auth.ha_ingress import HomeAssistantIngressPrincipalProvider
from hwa.db.base import Base
from hwa.db.engine import DatabaseSettings, create_engine
from hwa.db.models.identity import ExternalIdentityMapping, Person
from hwa.db.models.programme import ProgrammeDay
from hwa.domain.identity import PersonContext
from hwa.integrations.pep.ha_health_service import HaHealthServiceEnvelope
from hwa.integrations.pep.health_reader import PepHealthReader
from hwa.integrations.pep.service_assertion import ServiceAssertionSigner
from hwa.main import create_app
from hwa.services.programmes import import_week_seed
from hwa.web.dependencies import resolve_web_person_context

_spec = importlib.util.spec_from_file_location(
    "h6_web_responses", Path(__file__).parents[2] / "fixtures/pep_health_service_responses.py"
)
assert _spec is not None and _spec.loader is not None
_fixtures = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fixtures)


class HealthService:
    """Replace HA I/O only; independently verify each real signed assertion."""

    def __init__(self, key, failure=None):
        self.key = key
        self.failure = failure
        self.subjects = []
        self.jtis = []

    async def get_health_context(self, assertion):
        header, payload, signature = assertion.split(".")
        self.key.public_key().verify(
            base64.urlsafe_b64decode(signature + "=="), f"{header}.{payload}".encode("ascii")
        )
        claims = json.loads(base64.urlsafe_b64decode(payload + "=="))
        subject = claims["sub"]
        self.subjects.append(subject)
        self.jtis.append(claims["jti"])
        assert subject in {"synthetic-ha-a", "synthetic-ha-b"}
        if self.failure == "timeout":
            raise TimeoutError("synthetic-private-timeout")
        if self.failure == "disabled":
            return HaHealthServiceEnvelope(
                503, {"error": "HEALTH_AUTHORITY_DISABLED"}, {"Cache-Control": "no-store"}
            )
        suffix = "a" if subject == "synthetic-ha-a" else "b"
        projection = _fixtures.ready_projection(
            person_id=f"synthetic-pep-{suffix}", health_profile_id=f"synthetic-profile-{suffix}"
        )
        projection["body"]["body_mass"]["value"] = 81.3 if suffix == "a" else 62.4
        if self.failure == "invalid" or self.failure == "b-invalid" and suffix == "b":
            projection["person_id"] = "synthetic-pep-a" if suffix == "b" else "wrong-person"
        return HaHealthServiceEnvelope(200, projection, {"Cache-Control": "no-store"})


@pytest.fixture
def bound_app(tmp_path):
    engine = create_engine(DatabaseSettings(database_url=f"sqlite:///{tmp_path / 'h6-web.db'}"))
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        for suffix, name in (("a", "Synthetic A"), ("b", "Synthetic B")):
            person_id = f"synthetic-local-{suffix}"
            session.add(
                Person(
                    id=person_id,
                    canonical_key="kris" if suffix == "a" else "kirsty",
                    display_name=name,
                    presentation_profile="male" if suffix == "a" else "female",
                    active=True,
                )
            )
            session.flush()
            for authority, external_id in {
                "HOME_ASSISTANT": f"synthetic-ha-{suffix}",
                "PEP_SITE": f"synthetic-pep-{suffix}",
                "HEALTH_PROFILE": f"synthetic-profile-{suffix}",
                "MENU_NUTRITION": f"synthetic-menu-{suffix}",
            }.items():
                session.add(
                    ExternalIdentityMapping(
                        id=f"{person_id}-{authority}",
                        person_id=person_id,
                        authority=authority,
                        external_subject_id=external_id,
                    )
                )
        session.commit()
        import_week_seed(
            session,
            Path("programme_seed/home-workout-12m-v1/programme.json"),
            Path("programme_seed/home-workout-12m-v1/week-01.json"),
        )
    key = Ed25519PrivateKey.generate()
    counter = iter(range(100))
    signer = ServiceAssertionSigner(
        "synthetic-key", key, lambda: 1790841600.0, lambda: f"synthetic-jti-{next(counter)}"
    )
    service = HealthService(key)
    with Session(engine) as session:
        service.day_id = session.scalar(
            select(ProgrammeDay.id).where(
                ProgrammeDay.week_number == 1, ProgrammeDay.day_number == 1
            )
        )
    app = create_app(
        engine=engine,
        principal_provider=HomeAssistantIngressPrincipalProvider(trusted_hosts={"testclient"}),
        pep_health_reader=PepHealthReader(service_client=service, signer=signer),
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, app, service
    engine.dispose()


def _headers(suffix="a"):
    return {"X-Remote-User-Id": f"synthetic-ha-{suffix}"}


def _private_absent(response):
    for value in (
        "synthetic-ha-",
        "synthetic-local-",
        "synthetic-pep-",
        "synthetic-profile-",
        "synthetic-menu-",
        "synthetic-jti-",
        "synthetic-private-timeout",
    ):
        assert value not in response.text


def test_person_switch_signs_each_trusted_subject_and_isolates_values(bound_app):
    client, _, service = bound_app
    first = client.get("/", headers=_headers())
    second = client.get("/", headers=_headers("b"))
    assert first.status_code == second.status_code == 200
    assert "81.3 kg" in first.text and "62.4 kg" not in first.text
    assert "62.4 kg" in second.text and "81.3 kg" not in second.text
    assert "Synthetic A" not in second.text
    assert service.subjects == ["synthetic-ha-a", "synthetic-ha-b"]
    assert service.jtis == ["synthetic-jti-0", "synthetic-jti-1"]
    _private_absent(first)
    _private_absent(second)


@pytest.mark.parametrize("failure", ["timeout", "disabled", "b-invalid"])
def test_failed_b_read_after_a_success_never_reuses_a_context(bound_app, failure):
    client, _, service = bound_app
    first = client.get("/", headers=_headers())
    assert first.status_code == 200 and "81.3 kg" in first.text
    service.failure = failure
    second = client.get("/", headers=_headers("b"))
    assert second.status_code == 200
    assert 'class="home-context-rail"' not in second.text
    assert "81.3" not in second.text and "Synthetic A" not in second.text
    assert service.subjects == ["synthetic-ha-a", "synthetic-ha-b"]
    _private_absent(second)


def test_missing_trusted_request_principal_does_not_sign(bound_app):
    client, app, service = bound_app
    app.dependency_overrides[resolve_web_person_context] = lambda: PersonContext(
        hwa_person_id="synthetic-local-a",
        pep_person_id="synthetic-pep-a",
        health_profile_id="synthetic-profile-a",
        menu_person_id="synthetic-menu-a",
        presentation_profile="male",
        display_name="Synthetic A",
    )
    response = client.get("/", headers=_headers("b"))
    assert response.status_code == 200
    assert 'class="home-context-rail"' not in response.text
    assert service.subjects == []
    _private_absent(response)


@pytest.mark.parametrize(
    "selector",
    [
        "person_id",
        "hwa_person_id",
        "pep_person_id",
        "health_profile_id",
        "menu_person_id",
        "ha_user_id",
        "user_id",
        "subject_id",
        "sub",
        "source",
        "entity_id",
    ],
)
@pytest.mark.parametrize("location", ["query", "header", "form"])
def test_browser_selector_never_reaches_signing(bound_app, selector, location):
    client, _, service = bound_app
    headers = _headers()
    if location == "query":
        response = client.get("/", params={selector: "synthetic-ha-b"}, headers=headers)
    elif location == "header":
        headers[f"X-{selector.replace('_', '-')}"] = "synthetic-ha-b"
        response = client.get("/", headers=headers)
    else:
        response = client.post("/", data={selector: "synthetic-ha-b"}, headers=headers)
    assert response.status_code in {400, 405}
    assert service.subjects == []


@pytest.mark.parametrize("failure", ["unconfigured", "disabled", "timeout", "invalid"])
def test_workout_lifecycle_survives_health_failure(bound_app, failure):
    client, app, service = bound_app
    service.failure = failure
    if failure == "unconfigured":
        app.state.pep_health_reader = None
    headers = _headers()
    home = client.get("/", headers=headers)
    assert home.status_code == 200
    assert 'data-primary-action="start"' in home.text
    for path in ("/plan", "/workout", "/progress", "/more"):
        assert client.get(path, headers=headers).status_code == 200
    created = client.post(
        "/api/v1/workouts/drafts",
        headers=headers,
        json={
            "programme_day_id": service.day_id,
            "snapshot": {"phase": "WORKOUT_READY", "state_data": {}},
            "started_at": "2026-10-01T07:00:00Z",
        },
    )
    assert created.status_code == 201
    draft_id = created.json()["draft_id"]
    resumed = client.get("/", headers=headers)
    assert resumed.status_code == 200 and 'data-primary-action="resume"' in resumed.text
    active = client.get("/api/v1/workouts/drafts/active", headers=headers)
    assert active.status_code == 200 and active.json()["draft_id"] == draft_id
    completed = client.post(
        f"/api/v1/workouts/drafts/{draft_id}/complete",
        headers=headers,
        json={
            "idempotency_key": "synthetic-complete",
            "completed_at": "2026-10-01T07:42:00Z",
            "event": {
                "event_id": "synthetic-event",
                "source_event_id": "synthetic-event",
                "start_at": "2026-10-01T07:00:00Z",
                "end_at": "2026-10-01T07:42:00Z",
                "duration_seconds": 2520,
                "workout_type": "upper_body_bike",
                "programme": {
                    "programme_id": "home-workout-12m-v1",
                    "programme_week": 1,
                    "programme_day": 1,
                    "block": "foundation",
                },
                "effort": {"session_rpe": 6},
                "heart_rate_response": {"status": "UNAVAILABLE"},
                "training_load": {"status": "UNAVAILABLE"},
                "performance": {"completed": True, "strength": [], "cardio": []},
                "provenance": {
                    "authority": "HOME_WORKOUT_ASSISTANT",
                    "source_instance": "home-workout-assistant",
                    "recorded_at": "2026-10-01T07:42:00Z",
                },
            },
        },
    )
    assert completed.status_code == 201
    assert completed.json()["revision_number"] == 1
    assert completed.json()["event"]["person_id"] == "synthetic-local-a"
    assert client.get("/api/v1/workouts/drafts/active", headers=headers).status_code == 404
    _private_absent(resumed)
