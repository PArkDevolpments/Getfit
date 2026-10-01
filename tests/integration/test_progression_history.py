from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from hwa.db.base import Base
from hwa.db.engine import DatabaseSettings, create_engine
from hwa.db.models.identity import Person
from hwa.db.models.programme import ProgrammeDay, ProgrammeDefinition
from hwa.db.models.workout import WorkoutEvent, WorkoutRevision
from hwa.domain.progression import ProgressionAction, ProgressionRule
from hwa.domain.workout import CanonicalWorkoutEventV1
from hwa.services.progression import evaluate_strength_progression


def _event(
    event_id: str,
    person_id: str,
    *,
    reps: int,
    rpe: Decimal,
    rir: int,
) -> CanonicalWorkoutEventV1:
    start = datetime(2026, 10, 1, 17, 0, tzinfo=UTC)
    end = start + timedelta(minutes=30)
    return CanonicalWorkoutEventV1.model_validate(
        {
            "event_id": event_id,
            "source_event_id": f"source-{event_id}",
            "person_id": person_id,
            "start_at": start,
            "end_at": end,
            "duration_seconds": 1800,
            "workout_type": "strength",
            "programme": {
                "programme_id": "home-workout-12m-v1",
                "programme_week": 1,
                "programme_day": 1,
                "block": "foundation",
            },
            "effort": {"session_rpe": rpe},
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
                                "set_number": set_number,
                                "laterality": "BILATERAL",
                                "target_type": "REPS",
                                "load_value": Decimal("10.0"),
                                "load_unit": "KG",
                                "load_mode": "SINGLE_IMPLEMENT",
                                "reps": reps,
                                "duration_seconds": None,
                                "rir": rir,
                                "rpe": rpe,
                                "completed": True,
                                "pain_flag": False,
                            }
                            for set_number in (1, 2, 3)
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


def _session() -> tuple[Session, Engine]:
    engine = create_engine(DatabaseSettings(database_url="sqlite:///:memory:"))
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

    kris_v1 = _event("kris-event", "hwa-kris", reps=8, rpe=Decimal("8.0"), rir=2)
    kris_v2 = _event("kris-event", "hwa-kris", reps=10, rpe=Decimal("8.0"), rir=2)
    kirsty = _event("kirsty-event", "hwa-kirsty", reps=12, rpe=Decimal("6.0"), rir=3)
    session.add_all(
        [
            WorkoutEvent(
                event_id="kris-event",
                person_id="hwa-kris",
                programme_day_id="week1-day1",
                effective_revision_number=2,
                created_at_utc=kris_v1.end_at,
            ),
            WorkoutRevision(
                id="kris-r1",
                event_id="kris-event",
                revision_number=1,
                supersedes_revision_number=None,
                canonical_json=kris_v1.model_dump_json(by_alias=True),
                recorded_at_utc=kris_v1.end_at,
                correction_reason=None,
            ),
            WorkoutRevision(
                id="kris-r2",
                event_id="kris-event",
                revision_number=2,
                supersedes_revision_number=1,
                canonical_json=kris_v2.model_dump_json(by_alias=True),
                recorded_at_utc=kris_v2.end_at + timedelta(hours=1),
                correction_reason="Correct reps",
            ),
            WorkoutEvent(
                event_id="kirsty-event",
                person_id="hwa-kirsty",
                programme_day_id="week1-day1",
                effective_revision_number=1,
                created_at_utc=kirsty.end_at,
            ),
            WorkoutRevision(
                id="kirsty-r1",
                event_id="kirsty-event",
                revision_number=1,
                supersedes_revision_number=None,
                canonical_json=kirsty.model_dump_json(by_alias=True),
                recorded_at_utc=kirsty.end_at,
                correction_reason=None,
            ),
        ]
    )
    session.commit()
    return session, engine


def test_progression_uses_only_effective_person_evidence_without_rewriting_history() -> None:
    session, engine = _session()
    try:
        before_revisions = session.scalar(select(func.count()).select_from(WorkoutRevision))
        decision = evaluate_strength_progression(
            session,
            person_id="hwa-kris",
            exercise_id="goblet-squat",
            current_load=Decimal("10.0"),
            current_load_unit="KG",
            rule=ProgressionRule(
                rule_id="approved-double-progression-v1",
                required_completed_sessions=1,
                minimum_reps_per_set=10,
                maximum_rpe=Decimal("8.0"),
                minimum_rir=2,
                load_increment=Decimal("2.0"),
                load_unit="KG",
            ),
        )
        assert decision.action is ProgressionAction.PROPOSE_CHANGE
        assert decision.proposed_load == Decimal("12.0")
        assert len(decision.evidence_refs) == 1
        assert decision.evidence_refs[0].event_id == "kris-event"
        assert decision.evidence_refs[0].revision_number == 2
        assert session.scalar(select(func.count()).select_from(WorkoutRevision)) == before_revisions
        logical = session.get(WorkoutEvent, "kris-event")
        assert logical is not None
        assert logical.effective_revision_number == 2
    finally:
        session.close()
        engine.dispose()
