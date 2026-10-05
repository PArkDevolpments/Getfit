from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from hwa.auth.principal import StaticPrincipalProvider
from hwa.db.base import Base
from hwa.db.engine import DatabaseSettings, create_engine
from hwa.db.models.identity import ExternalIdentityMapping, Person
from hwa.db.models.programme import ProgrammeDay, ProgrammeDefinition
from hwa.db.models.workout import WorkoutEvent, WorkoutRevision
from hwa.domain.workout import CanonicalWorkoutEventV1
from hwa.main import create_app


def _event(event_id: str, person_id: str, reps: int) -> CanonicalWorkoutEventV1:
    start = datetime(2026, 10, 4, 17, 0, tzinfo=UTC)
    end = start + timedelta(minutes=25)
    return CanonicalWorkoutEventV1.model_validate(
        {
            "event_id": event_id,
            "source_event_id": f"source-{event_id}",
            "person_id": person_id,
            "start_at": start,
            "end_at": end,
            "duration_seconds": 1500,
            "workout_type": "strength",
            "programme": {
                "programme_id": "home-workout-12m-v1",
                "programme_week": 1,
                "programme_day": 1,
                "block": "foundation",
            },
            "effort": {"session_rpe": 7},
            "heart_rate_response": {"status": "UNAVAILABLE"},
            "training_load": {"status": "UNAVAILABLE"},
            "performance": {
                "completed": True,
                "strength": [
                    {
                        "exercise_id": "goblet_squat",
                        "completed": True,
                        "sets": [
                            {
                                "set_number": 1,
                                "laterality": "BILATERAL",
                                "target_type": "REPS",
                                "load_value": Decimal("10.0"),
                                "load_unit": "KG",
                                "load_mode": "SINGLE_IMPLEMENT",
                                "reps": reps,
                                "duration_seconds": None,
                                "rir": 2,
                                "rpe": Decimal("8.0"),
                                "completed": True,
                                "pain_flag": False,
                            }
                        ],
                    }
                ],
                "cardio": [],
            },
            "provenance": {
                "authority": "HOME_WORKOUT_ASSISTANT",
                "source_instance": "getfit-test",
                "recorded_at": end,
            },
        }
    )


def _client(tmp_path) -> tuple[TestClient, Engine]:
    engine = create_engine(
        DatabaseSettings(database_url=f"sqlite:///{tmp_path / 'analytics-surface.db'}")
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all(
            [
                Person(
                    id="hwa-a",
                    canonical_key="person-a",
                    display_name="Person A",
                    presentation_profile="primary",
                    active=True,
                ),
                Person(
                    id="hwa-b",
                    canonical_key="person-b",
                    display_name="Person B",
                    presentation_profile="secondary",
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
        for authority, subject in {
            "HOME_ASSISTANT": "ha-a",
            "PEP_SITE": "pep-a",
            "HEALTH_PROFILE": "health-a",
            "MENU_NUTRITION": "menu-a",
        }.items():
            session.add(
                ExternalIdentityMapping(
                    id=f"a-{authority}",
                    person_id="hwa-a",
                    authority=authority,
                    external_subject_id=subject,
                )
            )
        session.add(
            ProgrammeDay(
                id="week1-day1",
                programme_id="home-workout-12m-v1",
                week_number=1,
                day_number=1,
                title="Day 1",
                workout_type="strength",
                block="foundation",
            )
        )
        session.flush()
        for event_id, person_id, reps in (
            ("a-event", "hwa-a", 10),
            ("b-event", "hwa-b", 15),
        ):
            event = _event(event_id, person_id, reps)
            session.add(
                WorkoutEvent(
                    event_id=event_id,
                    person_id=person_id,
                    programme_day_id="week1-day1",
                    effective_revision_number=1,
                    created_at_utc=event.end_at,
                )
            )
            session.add(
                WorkoutRevision(
                    id=f"revision-{event_id}",
                    event_id=event_id,
                    revision_number=1,
                    supersedes_revision_number=None,
                    canonical_json=event.model_dump_json(by_alias=True),
                    recorded_at_utc=event.end_at,
                    correction_reason=None,
                )
            )
        session.commit()

    return (
        TestClient(
            create_app(
                principal_provider=StaticPrincipalProvider("ha-a"),
                engine=engine,
            )
        ),
        engine,
    )


def test_progress_surface_adds_descriptive_analytics_without_cross_person_data(tmp_path) -> None:
    client, engine = _client(tmp_path)
    try:
        response = client.get("/progress")
        assert response.status_code == 200
        html = response.text
        assert "Strength PRs" in html
        assert "13.3 kg e1RM" in html
        assert "Muscle coverage" in html
        assert "Quads" in html
        assert "12-week activity" in html
        assert "This is not a recovery or Health score." in html
        assert "Person B" not in html
    finally:
        client.close()
        engine.dispose()
