from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from hwa.db.base import Base
from hwa.db.engine import DatabaseSettings, create_engine
from hwa.db.models.identity import Person
from hwa.db.models.workout import WorkoutDraft, WorkoutEvent, WorkoutRevision
from hwa.services.programmes import import_week_seed
from hwa.web.review_sandbox import build_review_player, build_review_progress

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "programme_seed" / "home-workout-12m-v1" / "programme.json"
WEEK = ROOT / "programme_seed" / "home-workout-12m-v1" / "week-01.json"


def _session(tmp_path) -> tuple[Session, object]:
    engine = create_engine(
        DatabaseSettings(database_url=f"sqlite:///{tmp_path / 'review-sandbox.db'}")
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add(
        Person(
            id="hwa-kris",
            canonical_key="kris",
            display_name="Kris",
            presentation_profile="male",
            active=True,
        )
    )
    session.commit()
    import_week_seed(session, MANIFEST, WEEK)
    session.commit()
    return session, engine


def _count(session: Session, model: type[object]) -> int:
    return int(session.scalar(select(func.count()).select_from(model)) or 0)


def test_review_sandbox_uses_week1_authority_without_persisting_workout_state(tmp_path) -> None:
    session, engine = _session(tmp_path)
    try:
        before = (
            _count(session, WorkoutDraft),
            _count(session, WorkoutEvent),
            _count(session, WorkoutRevision),
        )

        strength = build_review_player(session, "hwa-kris", "strength-active")
        rest = build_review_player(session, "hwa-kris", "strength-rest")
        bike = build_review_player(session, "hwa-kris", "bike-finisher")
        hard = build_review_player(session, "hwa-kris", "interval-hard")
        recovery = build_review_player(session, "hwa-kris", "interval-recovery")

        floor_press = strength.strength[0]
        assert floor_press.exercise_id == "dumbbell_floor_press"
        assert floor_press.reps_target == 10
        assert str(floor_press.load_value) == "6.00"
        assert floor_press.load_mode == "EACH_HAND"
        assert floor_press.tempo_eccentric_seconds == 2
        assert floor_press.tempo_concentric_seconds == 1
        assert floor_press.media_path == "/static/media/exercises/dumbbell_floor_press.svg"

        assert rest.snapshot.phase.value == "REST_TIMER"
        assert rest.snapshot.state_data

        bike_target = next(item for item in bike.cardio if item.segment_type == "CONDITIONING")
        assert bike_target.duration_seconds == 900
        assert (bike_target.cadence_rpm_min, bike_target.cadence_rpm_max) == (80, 90)
        assert bike_target.resistance == "moderate"
        assert bike_target.rpe_min == Decimal("5")

        hard_target = next(item for item in hard.cardio if item.segment_type == "INTERVAL_HARD")
        assert hard_target.duration_seconds == 30
        assert hard_target.rounds == 5
        assert (hard_target.cadence_rpm_min, hard_target.cadence_rpm_max) == (85, 100)

        recovery_target = next(
            item for item in recovery.cardio if item.segment_type == "INTERVAL_RECOVERY"
        )
        assert recovery_target.duration_seconds == 90
        assert recovery_target.resistance == "light"

        after = (
            _count(session, WorkoutDraft),
            _count(session, WorkoutEvent),
            _count(session, WorkoutRevision),
        )
        assert after == before
    finally:
        session.close()
        engine.dispose()


def test_review_progress_is_isolated_and_exposes_populated_chart_component() -> None:
    progress = build_review_progress()

    assert progress.chart is not None
    assert progress.chart.exercise_id == "dumbbell_floor_press"
    assert len(progress.chart.points) == 4
    assert progress.chart.points[0].value_label == "6 kg"
    assert progress.chart.points[-1].value_label == "8 kg"
    assert progress.summary.completed_workouts == 4
    assert progress.summary.completion_percent == 100
