from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from hwa.db.base import Base
from hwa.db.engine import DatabaseSettings, create_engine
from hwa.db.models.identity import ExternalIdentityMapping, Person
from hwa.db.models.programme import ProgrammeDay, ProgrammeDefinition
from hwa.db.models.workout import WorkoutEvent, WorkoutRevision
from hwa.domain.workout import CanonicalWorkoutEventV1


def _event(
    *,
    event_id: str = "event-001",
    person_id: str = "hwa-kris",
    session_rpe: Decimal | None = Decimal("6.0"),
    completed: bool = True,
) -> CanonicalWorkoutEventV1:
    start = datetime(2026, 10, 1, 17, 0, tzinfo=UTC)
    end = start + timedelta(minutes=10)
    return CanonicalWorkoutEventV1.model_validate(
        {
            "event_id": event_id,
            "source_event_id": f"source-{event_id}",
            "person_id": person_id,
            "start_at": start,
            "end_at": end,
            "duration_seconds": 600,
            "workout_type": "strength_bike",
            "programme": {
                "programme_id": "home-workout-12m-v1",
                "programme_week": 1,
                "programme_day": 1,
                "block": "foundation",
            },
            "effort": {"session_rpe": session_rpe},
            "heart_rate_response": {"status": "UNAVAILABLE"},
            "training_load": {"status": "UNAVAILABLE"},
            "performance": {
                "completed": completed,
                "strength": [],
                "cardio": [],
            },
            "provenance": {
                "authority": "HOME_WORKOUT_ASSISTANT",
                "source_instance": "getfit-test",
                "recorded_at": end,
            },
        }
    )


def _session(database_url: str = "sqlite:///:memory:") -> tuple[Session, Engine]:
    engine = create_engine(DatabaseSettings(database_url=database_url))
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add_all(
        [
            Person(
                id="hwa-kris",
                canonical_key="kris",
                display_name="Kris",
                presentation_profile="male",
                active=True,
            ),
            Person(
                id="hwa-kirsty",
                canonical_key="kirsty",
                display_name="Kirsty",
                presentation_profile="female",
                active=True,
            ),
            ProgrammeDefinition(
                programme_id="home-workout-12m-v1",
                schema_version=1,
                title="Home Workout",
                active=True,
                seed_checksum="seed",
            ),
        ]
    )
    session.flush()
    session.add_all(
        [
            ExternalIdentityMapping(
                id="kris-pep",
                person_id="hwa-kris",
                authority="PEP_SITE",
                external_subject_id="person_a",
            ),
            ExternalIdentityMapping(
                id="kirsty-pep",
                person_id="hwa-kirsty",
                authority="PEP_SITE",
                external_subject_id="person_b",
            ),
            ProgrammeDay(
                id="day-1",
                programme_id="home-workout-12m-v1",
                week_number=1,
                day_number=1,
                title="Foundation",
                workout_type="mixed",
                block="foundation",
            ),
        ]
    )
    session.flush()
    event = _event()
    session.add(
        WorkoutEvent(
            event_id=event.event_id,
            person_id="hwa-kris",
            programme_day_id="day-1",
            effective_revision_number=1,
            created_at_utc=event.end_at,
        )
    )
    session.flush()
    session.add(
        WorkoutRevision(
            id="revision-1",
            event_id=event.event_id,
            revision_number=1,
            supersedes_revision_number=None,
            canonical_json=event.model_dump_json(by_alias=True),
            recorded_at_utc=event.end_at,
            correction_reason=None,
        )
    )
    session.commit()
    return session, engine


def test_provider_matches_pep_records_and_readiness_interface() -> None:
    from hwa.api.pep_export import PepWorkoutSourceProvider

    session, engine = _session()
    try:
        provider = PepWorkoutSourceProvider(session)
        readiness = provider.readiness("person_a")
        records = provider.records("person_a")

        assert readiness.ready is True
        assert readiness.state == "READY"
        assert readiness.reason == "OK"
        assert len(records) == 1
        row = records[0].model_dump(mode="json")
        assert row["person_id"] == "person_a"
        assert row["event_id"] == "event-001"
        assert row["start_at"] == "2026-10-01T17:00:00Z"
        assert row["end_at"] == "2026-10-01T17:10:00Z"
        assert row["duration"] == 600
        assert row["duration_unit"] == "seconds"
        assert row["effort"] == {"session_rpe": "6.0"}
        assert row["heart_rate_response"]["status"] == "UNAVAILABLE"
        assert row["training_load"]["status"] == "UNAVAILABLE"
        assert row["source_authority"] == "WORKOUT_EVENT_SOURCE"
        assert row["source_instance"] == "getfit-test"
        assert row["atomic_evidence_id"] == "revision-1"
        assert row["revision_number"] == 1
        assert row["provenance"]["authority"] == "HOME_WORKOUT_ASSISTANT"
        assert row["automatic_action"] is False
    finally:
        session.close()
        engine.dispose()


def test_provider_fails_closed_for_unmapped_pep_person() -> None:
    from hwa.api.pep_export import PepWorkoutSourceProvider

    session, engine = _session()
    try:
        provider = PepWorkoutSourceProvider(session)
        readiness = provider.readiness("person_unknown")
        assert readiness.ready is False
        assert readiness.state == "UNAVAILABLE"
        assert readiness.reason == "PERSON_NOT_MAPPED"
        assert provider.records("person_unknown") == ()
    finally:
        session.close()
        engine.dispose()


def test_provider_does_not_cross_person_fallback() -> None:
    from hwa.api.pep_export import PepWorkoutSourceProvider

    session, engine = _session()
    try:
        provider = PepWorkoutSourceProvider(session)
        assert provider.readiness("person_b").ready is True
        assert provider.records("person_b") == ()
    finally:
        session.close()
        engine.dispose()


def _machine_client(
    session_engine: Engine,
    credential: str | None,
    allowed_person_ids: frozenset[str] = frozenset({"person_a", "person_b"}),
) -> TestClient:
    from hwa.main import create_app

    return TestClient(
        create_app(
            engine=session_engine,
            pep_bridge_token=credential,
            pep_bridge_allowed_person_ids=allowed_person_ids,
        )
    )


def test_pep_machine_transport_fails_closed_without_configuration(tmp_path: Path) -> None:
    session, engine = _session(f"sqlite:///{tmp_path / 'hwa.db'}")
    session.close()
    try:
        response = _machine_client(engine, None).get(
            "/api/integrations/pep/v1/workouts/person_a"
        )
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "PEP_BRIDGE_NOT_CONFIGURED"
    finally:
        engine.dispose()


def test_pep_machine_transport_rejects_missing_wrong_and_ingress_only_auth(tmp_path: Path) -> None:
    session, engine = _session(f"sqlite:///{tmp_path / 'hwa.db'}")
    session.close()
    credential = "qa-only-machine-credential"
    client = _machine_client(engine, credential)
    try:
        missing = client.get("/api/integrations/pep/v1/workouts/person_a")
        wrong = client.get(
            "/api/integrations/pep/v1/workouts/person_a",
            headers={"Authorization": "Bearer not-the-credential"},
        )
        ingress_only = client.get(
            "/api/integrations/pep/v1/workouts/person_a",
            headers={"X-Remote-User-Id": "ha-admin"},
        )
        for response in (missing, wrong, ingress_only):
            assert response.status_code == 401
            assert response.json()["detail"]["code"] == "PEP_BRIDGE_AUTH_REQUIRED"
    finally:
        engine.dispose()


def test_pep_machine_transport_returns_only_requested_person_and_no_secret(tmp_path: Path) -> None:
    session, engine = _session(f"sqlite:///{tmp_path / 'hwa.db'}")
    session.close()
    credential = "qa-only-machine-credential"
    client = _machine_client(engine, credential)
    headers = {"Authorization": f"Bearer {credential}"}
    try:
        kris = client.get(
            "/api/integrations/pep/v1/workouts/person_a",
            headers=headers,
        )
        assert kris.status_code == 200
        body = kris.json()
        assert body["schema"] == "home-workout-assistant.pep-workout-export"
        assert body["schema_version"] == 1
        assert body["person_id"] == "person_a"
        snapshot = body["snapshot"]
        assert snapshot["schema"] == "home-workout-assistant.pep-workout-snapshot"
        assert snapshot["schema_version"] == 1
        assert snapshot["mode"] == "FULL_REPLACEMENT"
        assert snapshot["complete"] is True
        assert snapshot["generation"] == 1
        assert snapshot["record_count"] == 1
        assert snapshot["coverage"] == {
            "start_at": "2026-10-01T17:00:00Z",
            "end_at": "2026-10-01T17:10:00Z",
        }
        assert isinstance(snapshot["generated_at"], str) and snapshot["generated_at"]
        assert body["readiness"]["ready"] is True
        assert [row["person_id"] for row in body["records"]] == ["person_a"]
        assert [row["event_id"] for row in body["records"]] == ["event-001"]
        assert credential not in str(body)
        assert kris.headers["cache-control"] == "no-store"

        kirsty = client.get(
            "/api/integrations/pep/v1/workouts/person_b",
            headers=headers,
        )
        other = kirsty.json()
        assert kirsty.status_code == 200
        assert other["person_id"] == "person_b"
        assert other["schema_version"] == 1
        assert other["snapshot"] == {
            "schema": "home-workout-assistant.pep-workout-snapshot",
            "schema_version": 1,
            "mode": "FULL_REPLACEMENT",
            "complete": True,
            "generation": 0,
            "generated_at": other["snapshot"]["generated_at"],
            "record_count": 0,
            "coverage": {"start_at": None, "end_at": None},
        }
        assert other["readiness"]["ready"] is True
        assert other["records"] == []
    finally:
        engine.dispose()


def test_pep_machine_transport_unknown_person_has_no_cross_person_fallback(tmp_path: Path) -> None:
    session, engine = _session(f"sqlite:///{tmp_path / 'hwa.db'}")
    session.close()
    credential = "qa-only-machine-credential"
    try:
        response = _machine_client(engine, credential).get(
            "/api/integrations/pep/v1/workouts/person_unknown",
            headers={"Authorization": f"Bearer {credential}"},
        )
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "PEP_BRIDGE_PERSON_NOT_ALLOWED"
    finally:
        engine.dispose()


def test_pep_machine_transport_requires_explicit_service_person_scope(tmp_path: Path) -> None:
    from hwa.main import create_app

    session, engine = _session(f"sqlite:///{tmp_path / 'hwa.db'}")
    session.close()
    credential = "qa-only-machine-credential"
    app = create_app(engine=engine, pep_bridge_token=credential)
    app.state.pep_bridge_allowed_person_ids = frozenset({"person_a"})
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {credential}"}
    try:
        allowed = client.get(
            "/api/integrations/pep/v1/workouts/person_a",
            headers=headers,
        )
        assert allowed.status_code == 200

        denied = client.get(
            "/api/integrations/pep/v1/workouts/person_b",
            headers=headers,
        )
        assert denied.status_code == 403
        assert denied.json()["detail"]["code"] == "PEP_BRIDGE_PERSON_NOT_ALLOWED"
    finally:
        engine.dispose()


def test_pep_machine_transport_empty_service_scope_fails_closed(tmp_path: Path) -> None:
    from hwa.main import create_app

    session, engine = _session(f"sqlite:///{tmp_path / 'hwa.db'}")
    session.close()
    credential = "qa-only-machine-credential"
    app = create_app(engine=engine, pep_bridge_token=credential)
    app.state.pep_bridge_allowed_person_ids = frozenset()
    try:
        response = TestClient(app).get(
            "/api/integrations/pep/v1/workouts/person_a",
            headers={"Authorization": f"Bearer {credential}"},
        )
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "PEP_BRIDGE_PERSON_NOT_ALLOWED"
    finally:
        engine.dispose()


def test_pep_snapshot_generation_counts_all_revisions_not_only_effective_rows(
    tmp_path: Path,
) -> None:
    from hwa.main import create_app

    session, engine = _session(f"sqlite:///{tmp_path / 'hwa.db'}")
    event = session.get(WorkoutEvent, "event-001")
    assert event is not None
    original = _event()
    corrected = _event(session_rpe=Decimal("7.0"))
    session.add(
        WorkoutRevision(
            id="revision-2",
            event_id="event-001",
            revision_number=2,
            supersedes_revision_number=1,
            canonical_json=corrected.model_dump_json(by_alias=True),
            recorded_at_utc=corrected.end_at + timedelta(hours=1),
            correction_reason="QA correction",
        )
    )
    event.effective_revision_number = 2
    session.commit()
    session.close()

    credential = "qa-only-machine-credential"
    client = TestClient(
        create_app(
            engine=engine,
            pep_bridge_token=credential,
            pep_bridge_allowed_person_ids=frozenset({"person_a"}),
        )
    )
    try:
        response = client.get(
            "/api/integrations/pep/v1/workouts/person_a",
            headers={"Authorization": f"Bearer {credential}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["snapshot"]["complete"] is True
        assert body["snapshot"]["generation"] == 2
        assert body["snapshot"]["record_count"] == 1
        assert body["records"][0]["revision_number"] == 2
        assert body["records"][0]["event_id"] == original.event_id
    finally:
        engine.dispose()


def test_pep_full_snapshot_withdraws_no_longer_completed_effective_workout(
    tmp_path: Path,
) -> None:
    from hwa.main import create_app

    session, engine = _session(f"sqlite:///{tmp_path / 'hwa.db'}")
    logical = session.get(WorkoutEvent, "event-001")
    assert logical is not None
    withdrawn = _event(completed=False)
    session.add(
        WorkoutRevision(
            id="revision-withdrawn",
            event_id="event-001",
            revision_number=2,
            supersedes_revision_number=1,
            canonical_json=withdrawn.model_dump_json(by_alias=True),
            recorded_at_utc=withdrawn.end_at + timedelta(hours=2),
            correction_reason="Withdraw incorrectly completed workout",
        )
    )
    logical.effective_revision_number = 2
    session.commit()
    session.close()

    credential = "qa-only-machine-credential"
    client = TestClient(
        create_app(
            engine=engine,
            pep_bridge_token=credential,
            pep_bridge_allowed_person_ids=frozenset({"person_a"}),
        )
    )
    try:
        response = client.get(
            "/api/integrations/pep/v1/workouts/person_a",
            headers={"Authorization": f"Bearer {credential}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["schema_version"] == 1
        assert body["snapshot"]["mode"] == "FULL_REPLACEMENT"
        assert body["snapshot"]["complete"] is True
        assert body["snapshot"]["generation"] == 2
        assert body["snapshot"]["record_count"] == 0
        assert body["snapshot"]["coverage"] == {"start_at": None, "end_at": None}
        assert body["records"] == []
    finally:
        engine.dispose()


def test_pep_snapshot_fails_closed_if_generation_changes_during_read(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import hwa.api.pep_export as pep_export
    from hwa.main import create_app

    session, engine = _session(f"sqlite:///{tmp_path / 'hwa.db'}")
    session.close()
    observed = iter((1, 2))
    monkeypatch.setattr(
        pep_export,
        "workout_snapshot_generation_for_pep",
        lambda _session, _person: next(observed),
    )
    credential = "qa-only-machine-credential"
    client = TestClient(
        create_app(
            engine=engine,
            pep_bridge_token=credential,
            pep_bridge_allowed_person_ids=frozenset({"person_a"}),
        )
    )
    try:
        response = client.get(
            "/api/integrations/pep/v1/workouts/person_a",
            headers={"Authorization": f"Bearer {credential}"},
        )
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "PEP_WORKOUT_SNAPSHOT_CHANGED_DURING_READ"
    finally:
        engine.dispose()
