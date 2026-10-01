from datetime import UTC, datetime, timedelta
from decimal import Decimal

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
                "completed": True,
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
