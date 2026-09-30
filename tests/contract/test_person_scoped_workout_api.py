from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from hwa.auth.principal import StaticPrincipalProvider
from hwa.db.base import Base
from hwa.db.engine import DatabaseSettings, create_engine
from hwa.db.models.identity import ExternalIdentityMapping, Person
from hwa.db.models.programme import ProgrammeDay, ProgrammeDefinition
from hwa.main import create_app


def _seed(session: Session) -> None:
    people = [
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
    ]
    session.add_all(people)
    session.flush()
    mappings = {
        "hwa-kris": {
            "HOME_ASSISTANT": "ha-kris",
            "PEP_SITE": "person_a",
            "HEALTH_PROFILE": "kris",
            "MENU_NUTRITION": "person_1",
        },
        "hwa-kirsty": {
            "HOME_ASSISTANT": "ha-kirsty",
            "PEP_SITE": "person_b",
            "HEALTH_PROFILE": "kirsty",
            "MENU_NUTRITION": "person_2",
        },
    }
    for person_id, subjects in mappings.items():
        for authority, subject in subjects.items():
            session.add(
                ExternalIdentityMapping(
                    id=f"{person_id}-{authority}",
                    person_id=person_id,
                    authority=authority,
                    external_subject_id=subject,
                )
            )
    session.add(
        ProgrammeDefinition(
            programme_id="home-workout-12m-v1",
            schema_version=1,
            title="Home Workout 12 Month Programme",
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


def _clients(tmp_path):
    engine = create_engine(
        DatabaseSettings(database_url=f"sqlite:///{tmp_path / 'api.db'}")
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed(session)
    kris = TestClient(
        create_app(principal_provider=StaticPrincipalProvider("ha-kris"), engine=engine)
    )
    kirsty = TestClient(
        create_app(principal_provider=StaticPrincipalProvider("ha-kirsty"), engine=engine)
    )
    return kris, kirsty, engine


def _event_payload(session_rpe: int = 6) -> dict[str, object]:
    start = datetime(2026, 10, 1, 17, 0, tzinfo=UTC)
    end = start + timedelta(minutes=10)
    return {
        "event_id": "event-001",
        "source_event_id": "event-001",
        "start_at": start.isoformat(),
        "end_at": end.isoformat(),
        "duration_seconds": 600,
        "workout_type": "upper_body_bike",
        "programme": {
            "programme_id": "home-workout-12m-v1",
            "programme_week": 1,
            "programme_day": 1,
            "block": "foundation",
        },
        "effort": {"session_rpe": session_rpe},
        "heart_rate_response": {"status": "UNAVAILABLE"},
        "training_load": {"status": "UNAVAILABLE"},
        "performance": {"completed": True, "strength": [], "cardio": []},
        "provenance": {
            "authority": "HOME_WORKOUT_ASSISTANT",
            "source_instance": "home-workout-assistant",
            "recorded_at": end.isoformat(),
        },
    }


def test_workout_api_is_server_person_scoped_end_to_end(tmp_path) -> None:
    kris, kirsty, engine = _clients(tmp_path)
    try:
        spoofed = kris.post(
            "/api/v1/workouts/drafts",
            json={
                "person_id": "hwa-kirsty",
                "programme_day_id": "week1-day1",
                "snapshot": {"phase": "WORKOUT_READY", "state_data": {}},
                "started_at": "2026-10-01T17:00:00Z",
            },
        )
        assert spoofed.status_code == 422

        created = kris.post(
            "/api/v1/workouts/drafts",
            json={
                "programme_day_id": "week1-day1",
                "snapshot": {"phase": "WORKOUT_READY", "state_data": {}},
                "started_at": "2026-10-01T17:00:00Z",
            },
        )
        assert created.status_code == 201
        draft = created.json()
        assert draft["version"] == 1
        draft_id = draft["draft_id"]

        active = kris.get("/api/v1/workouts/drafts/active")
        assert active.status_code == 200
        assert active.json()["draft_id"] == draft_id
        assert kirsty.get("/api/v1/workouts/drafts/active").status_code == 404

        cross_person = kirsty.put(
            f"/api/v1/workouts/drafts/{draft_id}",
            json={
                "expected_version": 1,
                "snapshot": {"phase": "ACTIVE_SET", "state_data": {}},
                "saved_at": "2026-10-01T17:01:00Z",
            },
        )
        assert cross_person.status_code == 404

        saved = kris.put(
            f"/api/v1/workouts/drafts/{draft_id}",
            json={
                "expected_version": 1,
                "snapshot": {
                    "phase": "WORKOUT_SUMMARY",
                    "state_data": {"session_rpe": 6},
                },
                "saved_at": "2026-10-01T17:10:00Z",
            },
        )
        assert saved.status_code == 200
        assert saved.json()["version"] == 2

        stale = kris.put(
            f"/api/v1/workouts/drafts/{draft_id}",
            json={
                "expected_version": 1,
                "snapshot": {"phase": "WORKOUT_SUMMARY", "state_data": {}},
                "saved_at": "2026-10-01T17:11:00Z",
            },
        )
        assert stale.status_code == 409
        assert stale.json()["detail"]["code"] == "DRAFT_VERSION_CONFLICT"

        complete = kris.post(
            f"/api/v1/workouts/drafts/{draft_id}/complete",
            json={
                "idempotency_key": "complete-001",
                "completed_at": "2026-10-01T17:10:00Z",
                "event": _event_payload(),
            },
        )
        assert complete.status_code == 201
        assert complete.json()["revision_number"] == 1
        revision_id = complete.json()["revision_id"]

        replay = kris.post(
            f"/api/v1/workouts/drafts/{draft_id}/complete",
            json={
                "idempotency_key": "complete-001",
                "completed_at": "2026-10-01T17:10:00Z",
                "event": _event_payload(),
            },
        )
        assert replay.status_code == 200
        assert replay.json()["revision_id"] == revision_id

        assert kirsty.get("/api/v1/workouts/event-001").status_code == 404
        current = kris.get("/api/v1/workouts/event-001")
        assert current.status_code == 200
        assert current.json()["event"]["person_id"] == "hwa-kris"

        corrected = kris.post(
            "/api/v1/workouts/event-001/corrections",
            json={
                "idempotency_key": "correct-001",
                "reason": "Correct session RPE",
                "corrected_at": "2026-10-01T18:00:00Z",
                "event": _event_payload(session_rpe=7),
            },
        )
        assert corrected.status_code == 201
        assert corrected.json()["revision_number"] == 2
        assert corrected.json()["event"]["effort"]["session_rpe"] == "7"
    finally:
        engine.dispose()
