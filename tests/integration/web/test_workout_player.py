from datetime import UTC, datetime
from decimal import Decimal

from hwa.web.workout import build_player_context
from sqlalchemy.orm import Session

from hwa.db.base import Base
from hwa.db.engine import DatabaseSettings, create_engine
from hwa.db.models.identity import Person
from hwa.db.models.programme import (
    PersonPrescriptionOverride,
    ProgrammeCardioItem,
    ProgrammeDay,
    ProgrammeDefinition,
    ProgrammeStrengthItem,
)
from hwa.domain.draft import DraftPhase, WorkoutDraftSnapshot
from hwa.services.workout_drafts import create_draft


def _session(tmp_path) -> tuple[Session, object]:
    engine = create_engine(
        DatabaseSettings(database_url=f"sqlite:///{tmp_path / 'player.db'}")
    )
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
    session.commit()
    session.add(
        ProgrammeDay(
            id="day-1",
            programme_id="home-workout-12m-v1",
            week_number=1,
            day_number=1,
            title="Foundation A",
            workout_type="mixed",
            block="foundation",
        )
    )
    session.commit()
    session.add_all(
        [
            ProgrammeStrengthItem(
                id="strength-1",
                programme_day_id="day-1",
                sequence=1,
                exercise_id="goblet-squat",
                target_type="REPS",
                sets_target=3,
                reps_target=8,
                reps_min=8,
                reps_max=10,
                laterality="BILATERAL",
                load_value=Decimal("8.0"),
                load_unit="KG",
                load_mode="SINGLE_IMPLEMENT",
                load_basis="APPROVED_PROGRAMME",
                rest_seconds_min=60,
                rest_seconds_max=90,
                tempo_eccentric_seconds=3,
                tempo_concentric_seconds=1,
                notes="Controlled reps",
            ),
            ProgrammeCardioItem(
                id="cardio-1",
                programme_day_id="day-1",
                sequence=2,
                equipment="spin_bike",
                segment_type="steady",
                target_mode="DURATION",
                rounds=1,
                duration_seconds=600,
                cadence_rpm_min=70,
                cadence_rpm_max=85,
                resistance="moderate",
                rpe_min=Decimal("4.0"),
                rpe_max=Decimal("6.0"),
            ),
        ]
    )
    session.commit()
    session.add(
        PersonPrescriptionOverride(
            id="override-1",
            person_id="hwa-kris",
            programme_strength_item_id="strength-1",
            load_value=Decimal("10.0"),
            load_unit="KG",
            load_mode="SINGLE_IMPLEMENT",
            created_at_utc=datetime.now(UTC),
        )
    )
    session.commit()
    return session, engine


def _draft(session: Session, person_id: str) -> str:
    record = create_draft(
        session,
        person_id=person_id,
        programme_day_id="day-1",
        snapshot=WorkoutDraftSnapshot(phase=DraftPhase.WORKOUT_READY),
        started_at=datetime.now(UTC),
    )
    return record.id


def test_player_projects_approved_targets_and_person_override(tmp_path) -> None:
    session, engine = _session(tmp_path)
    try:
        draft_id = _draft(session, "hwa-kris")
        player = build_player_context(session, "hwa-kris", draft_id)

        assert player.display_name == "Kris"
        assert player.draft_id == draft_id
        assert player.draft_version == 1
        assert (player.week_number, player.day_number) == (1, 1)
        strength = player.strength[0]
        assert strength.exercise_id == "goblet-squat"
        assert strength.sets_target == 3
        assert strength.reps_min == 8
        assert strength.reps_max == 10
        assert strength.load_value == Decimal("10.0")
        assert strength.load_mode == "SINGLE_IMPLEMENT"
        assert strength.load_source == "PERSON_OVERRIDE"
    finally:
        session.close()
        engine.dispose()


def test_spin_bike_projection_never_exposes_incline_or_speed(tmp_path) -> None:
    session, engine = _session(tmp_path)
    try:
        player = build_player_context(session, "hwa-kris", _draft(session, "hwa-kris"))
        cardio = player.cardio[0]
        assert cardio.equipment == "SPIN_BIKE"
        assert cardio.speed_kmh is None
        assert cardio.incline_percent is None
        assert cardio.cadence_rpm_min == 70
        assert cardio.cadence_rpm_max == 85
        assert cardio.resistance == "moderate"
    finally:
        session.close()
        engine.dispose()


def test_player_is_person_scoped_and_does_not_borrow_kris_override(tmp_path) -> None:
    session, engine = _session(tmp_path)
    try:
        player = build_player_context(session, "hwa-kirsty", _draft(session, "hwa-kirsty"))
        assert player.display_name == "Kirsty"
        assert player.strength[0].load_value == Decimal("8.0")
        assert player.strength[0].load_source == "APPROVED_PROGRAMME"
    finally:
        session.close()
        engine.dispose()
