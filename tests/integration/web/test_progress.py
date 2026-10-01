from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from hwa.auth.principal import StaticPrincipalProvider
from hwa.db.base import Base
from hwa.db.engine import DatabaseSettings, create_engine
from hwa.db.models.identity import ExternalIdentityMapping, Person
from hwa.db.models.programme import ProgrammeDay, ProgrammeDefinition
from hwa.db.models.workout import WorkoutEvent, WorkoutRevision
from hwa.domain.workout import CanonicalWorkoutEventV1
from hwa.main import create_app


def _event(event_id: str, person_id: str, day: int, reps: int) -> CanonicalWorkoutEventV1:
    start = datetime(2026, 10, day, 17, 0, tzinfo=UTC)
    end = start + timedelta(minutes=25)
    return CanonicalWorkoutEventV1.model_validate(
        {
            "event_id": event_id,
            "source_event_id": f"source-{event_id}",
            "person_id": person_id,
            "start_at": start,
            "end_at": end,
            "duration_seconds": 1500,
            "workout_type": "mixed",
            "programme": {
                "programme_id": "home-workout-12m-v1",
                "programme_week": 1,
                "programme_day": day,
                "block": "foundation",
            },
            "effort": {"session_rpe": 6},
            "heart_rate_response": {"status": "UNAVAILABLE"},
            "training_load": {"status": "UNAVAILABLE"},
            "performance": {
                "completed": True,
                "strength": [
                    {
                        "exercise_id": "goblet-squat",
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
                                "rpe": Decimal("7.0"),
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


def _client(tmp_path) -> tuple[TestClient, object]:
    engine = create_engine(
        DatabaseSettings(database_url=f"sqlite:///{tmp_path / 'progress.db'}")
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
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
            for authority, external_subject_id in subjects.items():
                session.add(
                    ExternalIdentityMapping(
                        id=f"{person_id}-{authority}",
                        person_id=person_id,
                        authority=authority,
                        external_subject_id=external_subject_id,
                    )
                )
        for day in (1, 2, 3, 4):
            session.add(
                ProgrammeDay(
                    id=f"week1-day{day}",
                    programme_id="home-workout-12m-v1",
                    week_number=1,
                    day_number=day,
                    title=f"Day {day}",
                    workout_type="mixed",
                    block="foundation",
                )
            )
        session.flush()
        for event_id, person_id, day, reps in (
            ("kris-1", "hwa-kris", 1, 8),
            ("kris-2", "hwa-kris", 2, 10),
            ("kirsty-1", "hwa-kirsty", 3, 12),
        ):
            event = _event(event_id, person_id, day, reps)
            session.add(
                WorkoutEvent(
                    event_id=event_id,
                    person_id=person_id,
                    programme_day_id=f"week1-day{day}",
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
                principal_provider=StaticPrincipalProvider("ha-kris"),
                engine=engine,
            )
        ),
        engine,
    )


def test_progress_page_renders_only_effective_person_scoped_training_history(tmp_path) -> None:
    client, engine = _client(tmp_path)
    try:
        response = client.get("/progress")
        assert response.status_code == 200
        html = response.text
        assert "2 of 4 programme workouts completed" in html
        assert "50%" in html
        assert "Goblet Squat" in html
        assert "10 reps" in html
        assert "Kirsty" not in html
        assert "readiness" not in html.lower()
        assert "health status" not in html.lower()
    finally:
        client.close()
        engine.dispose()
