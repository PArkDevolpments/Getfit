from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from hwa.api.pep_export import PepWorkoutSourceProvider
from hwa.db.base import Base
from hwa.db.engine import DatabaseSettings, create_engine
from hwa.db.models.identity import ExternalIdentityMapping, Person
from hwa.db.models.programme import ProgrammeDay
from hwa.domain.workout import CanonicalWorkoutEventV1
from hwa.services.programmes import import_week_seed
from hwa.services.workout_drafts import create_draft
from hwa.services.workout_evidence import complete_workout, correct_workout

MANIFEST = Path("programme_seed/home-workout-12m-v1/programme.json")
WEEK = Path("programme_seed/home-workout-12m-v1/week-01.json")


def _event(rpe: int) -> CanonicalWorkoutEventV1:
    start = datetime(2026, 10, 1, 11, 0, tzinfo=UTC)
    end = start + timedelta(minutes=35)
    return CanonicalWorkoutEventV1.model_validate(
        {
            "event_id": "task12-correction-event",
            "source_event_id": "task12-correction-event",
            "person_id": "hwa-kris",
            "start_at": start,
            "end_at": end,
            "duration_seconds": 2100,
            "workout_type": "upper_body_bike",
            "programme": {
                "programme_id": "home-workout-12m-v1",
                "programme_week": 1,
                "programme_day": 1,
                "block": "foundation",
            },
            "effort": {"session_rpe": rpe},
            "heart_rate_response": {"status": "UNAVAILABLE"},
            "training_load": {"status": "UNAVAILABLE"},
            "performance": {"completed": True, "strength": [], "cardio": []},
            "provenance": {
                "authority": "HOME_WORKOUT_ASSISTANT",
                "source_instance": "home-workout-assistant",
                "recorded_at": end,
            },
        }
    )


def test_only_effective_revision_is_projected_to_pep(tmp_path) -> None:
    engine = create_engine(DatabaseSettings(database_url=f"sqlite:///{tmp_path / 'r.db'}"))
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Person(id="hwa-kris", canonical_key="kris", display_name="Kris", presentation_profile="male", active=True))
        session.flush()
        session.add(ExternalIdentityMapping(id="pep-kris", person_id="hwa-kris", authority="PEP_SITE", external_subject_id="person_a"))
        session.commit()
        import_week_seed(session, MANIFEST, WEEK)
        day = session.scalar(select(ProgrammeDay).where(ProgrammeDay.week_number == 1, ProgrammeDay.day_number == 1))
        assert day is not None
        draft = create_draft(session, person_id="hwa-kris", programme_day_id=day.id, snapshot={"phase": "WORKOUT_READY", "state_data": {}}, started_at=datetime(2026, 10, 1, 11, 0, tzinfo=UTC))
        first = complete_workout(session, person_id="hwa-kris", draft_id=draft.id, idempotency_key="complete", event=_event(6), completed_at=datetime(2026, 10, 1, 11, 35, tzinfo=UTC))
        second = correct_workout(session, person_id="hwa-kris", event_id=first.event_id, idempotency_key="correct", event=_event(7), reason="Correct effort", corrected_at=datetime(2026, 10, 1, 11, 50, tzinfo=UTC))
        records = PepWorkoutSourceProvider(session).records("person_a")
        assert len(records) == 1
        assert records[0].revision_number == 2
        assert records[0].supersedes_revision_number == 1
        assert str(records[0].session_rpe) == "7"
        assert records[0].provenance.atomic_evidence_id == second.revision_id
    engine.dispose()
