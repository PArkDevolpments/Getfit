"""Read-only review sandbox states built from approved programme authority.

These projections never create drafts, workout events or revisions. They exist only so
the browser audit can render deterministic states without mutating live training data.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Literal

from pydantic import JsonValue
from sqlalchemy import select
from sqlalchemy.orm import Session

from hwa.db.models.identity import Person
from hwa.db.models.programme import ProgrammeDay
from hwa.domain.draft import DraftPhase, WorkoutDraftSnapshot
from hwa.read_models.history import WorkoutHistoryRow
from hwa.read_models.progress import ExerciseProgressSummary, ProgressSummary
from hwa.read_models.training_analytics import (
    ActivityDay,
    ExercisePersonalBest,
    MuscleCoverageRow,
    TrainingAnalytics,
)
from hwa.web.progress import (
    ProgressChartPoint,
    ProgressChartSeries,
    ProgressPageContext,
)
from hwa.web.workout import (
    WorkoutPlayerContext,
    get_cardio_targets,
    get_strength_targets,
)

PROGRAMME_ID = "home-workout-12m-v1"


def _day(session: Session, day_number: int) -> ProgrammeDay:
    day = session.scalar(
        select(ProgrammeDay).where(
            ProgrammeDay.programme_id == PROGRAMME_ID,
            ProgrammeDay.week_number == 1,
            ProgrammeDay.day_number == day_number,
        )
    )
    if day is None:
        raise LookupError(f"Week 1 Day {day_number} is not available")
    return day


def build_review_player(
    session: Session,
    person_id: str,
    state: str,
) -> WorkoutPlayerContext:
    """Build a deterministic non-persistent workout player state."""

    person = session.get(Person, person_id)
    if person is None or not person.active:
        raise LookupError(person_id)

    day_number = {
        "strength-active": 1,
        "strength-feedback": 1,
        "strength-pain": 1,
        "strength-rest": 1,
        "bike-finisher": 1,
        "treadmill": 2,
        "interval-hard": 4,
        "interval-recovery": 4,
    }.get(state)
    if day_number is None:
        raise LookupError(state)

    day = _day(session, day_number)
    strength = get_strength_targets(session, person_id, day.id)
    cardio = get_cardio_targets(session, day.id)
    state_data: dict[str, JsonValue] = {}

    current_kind: Literal["STRENGTH", "CARDIO"] = "STRENGTH"
    current_sequence = 1
    current_set_number: int | None = 1
    phase = DraftPhase.ACTIVE_SET

    if state in {"strength-feedback", "strength-pain", "strength-rest"} and strength:
        first = strength[0]
        state_data[f"{first.item_id}-set-1-reps"] = first.reps_target or first.reps_min or 10
        if first.load_value is not None:
            state_data[f"{first.item_id}-set-1-load"] = float(first.load_value)
        state_data[f"{first.item_id}-set-1-rpe"] = 8
        state_data[f"{first.item_id}-set-1-rir"] = 2
        state_data[f"{first.item_id}-set-1-completed"] = True
        if state == "strength-pain":
            state_data[f"{first.item_id}-set-1-pain"] = True
            state_data["__pain_stop_item"] = first.item_id
        phase = (
            DraftPhase.REST_TIMER
            if state == "strength-rest"
            else DraftPhase.SET_FEEDBACK
        )

    if state in {"bike-finisher", "treadmill", "interval-hard", "interval-recovery"}:
        current_kind = "CARDIO"
        current_set_number = None
        phase = DraftPhase.CARDIO_COOLDOWN
        segment = {
            "bike-finisher": "CONDITIONING",
            "treadmill": "STEADY",
            "interval-hard": "INTERVAL_HARD",
            "interval-recovery": "INTERVAL_RECOVERY",
        }[state]
        current = next(item for item in cardio if item.segment_type.upper() == segment)
        current_sequence = current.sequence

    snapshot = WorkoutDraftSnapshot(
        phase=phase,
        current_item_kind=current_kind,
        current_sequence=current_sequence,
        current_set_number=current_set_number,
        state_data=state_data,
    )

    return WorkoutPlayerContext(
        display_name=person.display_name,
        presentation_profile=person.presentation_profile,
        draft_id=f"review-sandbox-{state}",
        draft_version=1,
        started_at=datetime(2026, 10, 2, 12, 0, tzinfo=UTC),
        snapshot=snapshot,
        programme_day_id=day.id,
        week_number=day.week_number,
        day_number=day.day_number,
        title=day.title,
        workout_type=day.workout_type,
        block=day.block,
        strength=strength,
        cardio=cardio,
    )


def build_review_progress() -> ProgressPageContext:
    """Return isolated review evidence for the Progress visual component."""

    points = (
        ProgressChartPoint("W1", Decimal("6"), "6 kg", 50, 205),
        ProgressChartPoint("W2", Decimal("6.5"), "6.5 kg", 215, 170),
        ProgressChartPoint("W3", Decimal("7"), "7 kg", 380, 125),
        ProgressChartPoint("W4", Decimal("8"), "8 kg", 550, 65),
    )
    chart = ProgressChartSeries(
        exercise_id="dumbbell_floor_press",
        display_name="Dumbbell Floor Press",
        metric_name="Load (kg)",
        points=points,
        polyline=" ".join(f"{point.x},{point.y}" for point in points),
        min_label="6 kg",
        max_label="8 kg",
    )
    summaries = (
        ExerciseProgressSummary(
            exercise_id="dumbbell_floor_press",
            sessions=4,
            latest_total_reps=20,
            latest_total_duration_seconds=0,
            latest_max_recorded_load_kg=Decimal("8"),
            latest_completed_sets=2,
        ),
        ExerciseProgressSummary(
            exercise_id="one_arm_dumbbell_row",
            sessions=4,
            latest_total_reps=40,
            latest_total_duration_seconds=0,
            latest_max_recorded_load_kg=Decimal("10"),
            latest_completed_sets=4,
        ),
        ExerciseProgressSummary(
            exercise_id="goblet_squat",
            sessions=3,
            latest_total_reps=20,
            latest_total_duration_seconds=0,
            latest_max_recorded_load_kg=Decimal("10"),
            latest_completed_sets=2,
        ),
    )
    summary = ProgressSummary(
        completed_workouts=4,
        available_programme_workouts=4,
        completion_percent=100,
        latest_programme_week=1,
        latest_programme_day=4,
        exercise_summaries=summaries,
    )
    history = tuple(
        WorkoutHistoryRow(
            event_id=f"review-event-{day}",
            revision_number=1,
            start_at=datetime(2026, 9, 20 + day, 18, 0, tzinfo=UTC),
            end_at=datetime(2026, 9, 20 + day, 18, 42, tzinfo=UTC),
            duration_seconds=2520,
            workout_type=workout_type,
            programme_id=PROGRAMME_ID,
            programme_week=1,
            programme_day=day,
            block="foundation",
            session_rpe=Decimal("6"),
            completed=True,
            correction_reason=None,
        )
        for day, workout_type in (
            (4, "conditioning"),
            (3, "full_body_bike"),
            (2, "lower_body_core"),
            (1, "upper_body_bike"),
        )
    )
    analytics_anchor = date(2026, 10, 4)
    personal_bests = (
        ExercisePersonalBest(
            exercise_id="dumbbell_floor_press",
            display_name="Dumbbell Floor Press",
            sessions=4,
            best_load_kg=Decimal("8"),
            estimated_1rm_kg=Decimal("10.7"),
            best_reps=10,
            last_performed_at=datetime(2026, 10, 4, 18, 20, tzinfo=UTC),
        ),
        ExercisePersonalBest(
            exercise_id="one_arm_dumbbell_row",
            display_name="One-arm Dumbbell Row",
            sessions=4,
            best_load_kg=Decimal("10"),
            estimated_1rm_kg=Decimal("13.3"),
            best_reps=10,
            last_performed_at=datetime(2026, 10, 4, 18, 28, tzinfo=UTC),
        ),
        ExercisePersonalBest(
            exercise_id="goblet_squat",
            display_name="Goblet Squat",
            sessions=3,
            best_load_kg=Decimal("10"),
            estimated_1rm_kg=Decimal("14.0"),
            best_reps=12,
            last_performed_at=datetime(2026, 10, 3, 18, 16, tzinfo=UTC),
        ),
    )
    muscle_coverage = (
        MuscleCoverageRow(
            muscle_id="chest",
            display_name="Chest",
            recent_set_equivalents=Decimal("8.0"),
            intensity_percent=80,
            last_trained_at=datetime(2026, 10, 4, 18, 20, tzinfo=UTC),
        ),
        MuscleCoverageRow(
            muscle_id="back",
            display_name="Back",
            recent_set_equivalents=Decimal("10.0"),
            intensity_percent=100,
            last_trained_at=datetime(2026, 10, 4, 18, 28, tzinfo=UTC),
        ),
        MuscleCoverageRow(
            muscle_id="shoulders",
            display_name="Shoulders",
            recent_set_equivalents=Decimal("6.0"),
            intensity_percent=60,
            last_trained_at=datetime(2026, 10, 4, 18, 34, tzinfo=UTC),
        ),
        MuscleCoverageRow(
            muscle_id="quads",
            display_name="Quads",
            recent_set_equivalents=Decimal("7.0"),
            intensity_percent=70,
            last_trained_at=datetime(2026, 10, 3, 18, 16, tzinfo=UTC),
        ),
        MuscleCoverageRow(
            muscle_id="glutes",
            display_name="Glutes",
            recent_set_equivalents=Decimal("5.5"),
            intensity_percent=55,
            last_trained_at=datetime(2026, 10, 3, 18, 16, tzinfo=UTC),
        ),
        MuscleCoverageRow(
            muscle_id="hamstrings",
            display_name="Hamstrings",
            recent_set_equivalents=Decimal("3.0"),
            intensity_percent=30,
            last_trained_at=datetime(2026, 10, 3, 18, 26, tzinfo=UTC),
        ),
        MuscleCoverageRow(
            muscle_id="biceps",
            display_name="Biceps",
            recent_set_equivalents=Decimal("5.0"),
            intensity_percent=50,
            last_trained_at=datetime(2026, 10, 4, 18, 28, tzinfo=UTC),
        ),
        MuscleCoverageRow(
            muscle_id="triceps",
            display_name="Triceps",
            recent_set_equivalents=Decimal("4.0"),
            intensity_percent=40,
            last_trained_at=datetime(2026, 10, 4, 18, 20, tzinfo=UTC),
        ),
        MuscleCoverageRow(
            muscle_id="core",
            display_name="Core",
            recent_set_equivalents=Decimal("4.5"),
            intensity_percent=45,
            last_trained_at=datetime(2026, 10, 3, 18, 34, tzinfo=UTC),
        ),
    )
    active_activity = {
        analytics_anchor - timedelta(days=offset): (workouts, sets, level)
        for offset, workouts, sets, level in (
            (0, 1, 10, 3),
            (1, 1, 8, 3),
            (2, 1, 6, 2),
            (3, 1, 8, 3),
            (7, 1, 10, 3),
            (9, 1, 5, 2),
            (12, 1, 4, 2),
            (15, 1, 8, 3),
            (20, 1, 3, 1),
            (22, 1, 9, 3),
            (28, 1, 6, 2),
            (35, 1, 5, 2),
            (43, 1, 4, 2),
            (49, 1, 8, 3),
            (57, 1, 3, 1),
            (64, 1, 6, 2),
            (71, 1, 4, 2),
            (78, 1, 5, 2),
        )
    }
    activity_days = tuple(
        ActivityDay(
            day=current,
            workout_count=active_activity.get(current, (0, 0, 0))[0],
            completed_sets=active_activity.get(current, (0, 0, 0))[1],
            intensity_level=active_activity.get(current, (0, 0, 0))[2],
        )
        for current in (
            analytics_anchor - timedelta(days=83 - offset)
            for offset in range(84)
        )
    )
    analytics = TrainingAnalytics(
        personal_bests=personal_bests,
        muscle_coverage=muscle_coverage,
        activity_days=activity_days,
    )
    return ProgressPageContext(
        summary=summary,
        history=history,
        chart=chart,
        analytics=analytics,
    )
