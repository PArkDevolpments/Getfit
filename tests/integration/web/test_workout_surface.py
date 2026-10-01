from datetime import UTC, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from hwa.auth.principal import StaticPrincipalProvider
from hwa.db.base import Base
from hwa.db.engine import DatabaseSettings, create_engine
from hwa.db.models.identity import ExternalIdentityMapping, Person
from hwa.db.models.programme import (
    ProgrammeCardioItem,
    ProgrammeDay,
    ProgrammeDefinition,
    ProgrammeStrengthItem,
)
from hwa.domain.draft import DraftPhase, WorkoutDraftSnapshot
from hwa.main import create_app
from hwa.services.workout_drafts import create_draft


def _client(tmp_path, subject: str = "ha-kris") -> tuple[TestClient, object]:
    engine = create_engine(
        DatabaseSettings(database_url=f"sqlite:///{tmp_path / 'workout-surface.db'}")
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
        for person_id, ha_subject in (
            ("hwa-kris", "ha-kris"),
            ("hwa-kirsty", "ha-kirsty"),
        ):
            session.add(
                ExternalIdentityMapping(
                    id=f"{person_id}-ha",
                    person_id=person_id,
                    authority="HOME_ASSISTANT",
                    external_subject_id=ha_subject,
                )
            )
        session.add(
            ProgrammeDay(
                id="week1-day1",
                programme_id="home-workout-12m-v1",
                week_number=1,
                day_number=1,
                title="Strength + Bike",
                workout_type="mixed",
                block="foundation",
            )
        )
        session.flush()
        session.add_all(
            [
                ProgrammeStrengthItem(
                    id="strength-1",
                    programme_day_id="week1-day1",
                    sequence=1,
                    exercise_id="goblet-squat",
                    target_type="REPS",
                    sets_target=2,
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
                ),
                ProgrammeCardioItem(
                    id="bike-1",
                    programme_day_id="week1-day1",
                    sequence=2,
                    equipment="SPIN_BIKE",
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
        if subject == "ha-kris":
            create_draft(
                session,
                person_id="hwa-kris",
                programme_day_id="week1-day1",
                snapshot=WorkoutDraftSnapshot(
                    phase=DraftPhase.ACTIVE_SET,
                    current_item_kind="STRENGTH",
                    current_sequence=1,
                    current_set_number=1,
                    state_data={"note": "server-saved"},
                ),
                started_at=datetime(2026, 10, 1, 7, 0, tzinfo=UTC),
            )
    return (
        TestClient(
            create_app(
                principal_provider=StaticPrincipalProvider(subject),
                engine=engine,
            )
        ),
        engine,
    )


def test_workout_surface_renders_active_server_draft_and_controls(tmp_path) -> None:
    client, engine = _client(tmp_path)
    try:
        response = client.get("/workout")
        assert response.status_code == 200
        html = response.text
        assert "Strength + Bike" in html
        assert "goblet-squat" in html
        assert 'data-draft-version="1"' in html
        assert 'data-autosave-url="/api/v1/workouts/drafts/' in html
        assert 'data-complete-url="/api/v1/workouts/drafts/' in html
        assert 'name="strength-1-set-1-reps"' in html
        assert 'name="strength-1-set-1-rpe"' in html
        assert 'name="strength-1-set-1-rir"' in html
        assert 'name="bike-1-duration"' in html
        assert 'name="bike-1-cadence-min"' in html
        assert 'name="bike-1-cadence-max"' in html
        assert 'name="bike-1-resistance"' in html
        assert 'name="bike-1-speed"' not in html
        assert 'name="bike-1-incline"' not in html
        assert "server-saved" in html
        assert "/static/workout.js" in html
        assert 'id="complete-workout"' in html
        assert "Kirsty" not in html
    finally:
        client.close()
        engine.dispose()


def test_workout_surface_without_active_draft_fails_closed_without_borrowing(tmp_path) -> None:
    client, engine = _client(tmp_path, subject="ha-kirsty")
    try:
        response = client.get("/workout")
        assert response.status_code == 200
        assert 'data-workout-state="no-active-draft"' in response.text
        assert "No workout is currently in progress" in response.text
        assert "server-saved" not in response.text
        assert "Kris" not in response.text
    finally:
        client.close()
        engine.dispose()


def test_workout_script_has_version_conflict_and_idempotent_completion_guards() -> None:
    script = (
        __import__("pathlib")
        .Path("src/hwa/web/static/workout.js")
        .read_text(encoding="utf-8")
    )
    assert "expected_version" in script
    assert "DRAFT_VERSION_CONFLICT" in script
    assert "idempotency_key" in script
    assert "complete:" in script
    assert "crypto.randomUUID" not in script
