from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from hwa.api.pep_export import PepWorkoutSourceProvider
from hwa.auth.principal import StaticPrincipalProvider
from hwa.db.base import Base
from hwa.db.engine import DatabaseSettings, create_engine
from hwa.db.models.identity import ExternalIdentityMapping, Person
from hwa.db.models.programme import ProgrammeDay
from hwa.main import create_app
from hwa.services.programmes import import_week_seed

PROGRAMME_MANIFEST = Path("programme_seed/home-workout-12m-v1/programme.json")
WEEK_ONE = Path("programme_seed/home-workout-12m-v1/week-01.json")


def _seed(session: Session) -> str:
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
    import_week_seed(session, PROGRAMME_MANIFEST, WEEK_ONE)
    day = session.scalar(
        select(ProgrammeDay).where(
            ProgrammeDay.programme_id == "home-workout-12m-v1",
            ProgrammeDay.week_number == 1,
            ProgrammeDay.day_number == 1,
        )
    )
    assert day is not None
    return day.id


def _event_payload() -> dict[str, object]:
    started = datetime(2026, 10, 1, 7, 0, tzinfo=UTC)
    ended = started + timedelta(minutes=42)
    return {
        "event_id": "task12-kris-event",
        "source_event_id": "task12-kris-event",
        "start_at": started.isoformat(),
        "end_at": ended.isoformat(),
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
        "performance": {
            "completed": True,
            "strength": [
                {
                    "exercise_id": "dumbbell_floor_press",
                    "completed": True,
                    "sets": [
                        {
                            "set_number": 1,
                            "laterality": "BILATERAL",
                            "target_type": "REPS",
                            "completed": True,
                            "pain_flag": False,
                            "reps": 10,
                            "load_value": 6,
                            "load_unit": "KG",
                            "load_mode": "EACH_HAND",
                            "rpe": 6,
                            "rir": 3,
                        }
                    ],
                }
            ],
            "cardio": [
                {
                    "equipment": "SPIN_BIKE",
                    "duration_seconds": 900,
                    "cadence_rpm_min": 85,
                    "cadence_rpm_max": 85,
                    "resistance": "moderate",
                    "rpe": 5,
                    "completed": True,
                }
            ],
        },
        "provenance": {
            "authority": "HOME_WORKOUT_ASSISTANT",
            "source_instance": "home-workout-assistant",
            "recorded_at": ended.isoformat(),
        },
    }


def test_kris_can_start_interrupt_resume_complete_review_and_export(tmp_path) -> None:
    db_path = tmp_path / "task12.db"
    settings = DatabaseSettings(database_url=f"sqlite:///{db_path}")
    engine = create_engine(settings)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        day_id = _seed(session)

    client = TestClient(
        create_app(principal_provider=StaticPrincipalProvider("ha-kris"), engine=engine)
    )
    try:
        for path in ("/", "/workout", "/progress", "/library", "/settings"):
            response = client.get(path)
            assert response.status_code == 200
            assert "Kris" in response.text

        today = client.get("/")
        assert 'data-primary-action="start"' in today.text
        assert "Health context unavailable" in today.text
        assert "Nutrition context unavailable" in today.text

        created = client.post(
            "/api/v1/workouts/drafts",
            json={
                "programme_day_id": day_id,
                "snapshot": {"phase": "WORKOUT_READY", "state_data": {}},
                "started_at": "2026-10-01T07:00:00Z",
            },
        )
        assert created.status_code == 201
        draft = created.json()

        saved = client.put(
            f"/api/v1/workouts/drafts/{draft['draft_id']}",
            json={
                "expected_version": draft["version"],
                "snapshot": {
                    "phase": "ACTIVE_SET",
                    "current_item_kind": "STRENGTH",
                    "current_sequence": 1,
                    "current_set_number": 1,
                    "state_data": {
                        "reps": 10,
                        "load_kg_each_hand": 6,
                        "spin_bike_cadence_rpm": 85,
                        "spin_bike_resistance": "moderate",
                    },
                },
                "saved_at": "2026-10-01T07:15:00Z",
            },
        )
        assert saved.status_code == 200
        assert saved.json()["version"] == 2
    finally:
        client.close()
        engine.dispose()

    restarted_engine = create_engine(settings)
    restarted = TestClient(
        create_app(
            principal_provider=StaticPrincipalProvider("ha-kris"),
            engine=restarted_engine,
        )
    )
    try:
        resume = restarted.get("/")
        assert resume.status_code == 200
        assert 'data-primary-action="resume"' in resume.text
        assert draft["draft_id"] in resume.text

        completed = restarted.post(
            f"/api/v1/workouts/drafts/{draft['draft_id']}/complete",
            json={
                "idempotency_key": "task12-complete-1",
                "completed_at": "2026-10-01T07:42:00Z",
                "event": _event_payload(),
            },
        )
        assert completed.status_code == 201
        assert completed.json()["revision_number"] == 1

        progress = restarted.get("/progress")
        assert progress.status_code == 200
        assert "1 of 4 programme workouts completed" in progress.text
        assert "task12-kris-event" not in progress.text
        assert "Dumbbell Floor Press" in progress.text

        with Session(restarted_engine) as session:
            provider = PepWorkoutSourceProvider(session)
            assert provider.readiness("person_a").ready is True
            records = provider.records("person_a")
            assert len(records) == 1
            assert records[0].event_id == "task12-kris-event"
            assert records[0].revision_number == 1
            assert records[0].duration == 2520
            assert str(records[0].effort.session_rpe) == "6"
    finally:
        restarted.close()
        restarted_engine.dispose()
