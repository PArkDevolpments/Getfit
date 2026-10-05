"""Descriptive strength and consistency analytics from effective Getfit evidence.

These metrics never alter programme prescription or workout history. They deliberately use only
person-scoped effective revisions and label estimates as estimates.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from hwa.domain.exercise_catalog import (
    MUSCLE_LABELS,
    MUSCLE_ORDER,
    display_name,
    exercise_profile,
)
from hwa.read_models.history import (
    StrengthSetHistoryRow,
    get_strength_set_history,
    get_workout_history,
)

_ONE_DECIMAL = Decimal("0.1")
_PRIMARY_SET_WEIGHT = Decimal("1.0")
_SECONDARY_SET_WEIGHT = Decimal("0.5")


@dataclass(frozen=True, slots=True)
class ExercisePersonalBest:
    exercise_id: str
    display_name: str
    sessions: int
    best_load_kg: Decimal | None
    estimated_1rm_kg: Decimal | None
    best_reps: int | None
    last_performed_at: datetime


@dataclass(frozen=True, slots=True)
class MuscleCoverageRow:
    muscle_id: str
    display_name: str
    recent_set_equivalents: Decimal
    intensity_percent: int
    last_trained_at: datetime | None


@dataclass(frozen=True, slots=True)
class ActivityDay:
    day: date
    workout_count: int
    completed_sets: int
    intensity_level: int


@dataclass(frozen=True, slots=True)
class TrainingAnalytics:
    personal_bests: tuple[ExercisePersonalBest, ...]
    muscle_coverage: tuple[MuscleCoverageRow, ...]
    activity_days: tuple[ActivityDay, ...]


def estimate_epley_1rm(load_kg: Decimal, reps: int) -> Decimal | None:
    """Estimate 1RM using Epley for completed loaded sets of 1-15 reps.

    Higher-rep sets are deliberately excluded because the estimate becomes too noisy to present as
    a useful training metric. The returned value remains on the recorded load basis (for example,
    each-hand when that is how the set was recorded).
    """

    if load_kg <= 0 or reps <= 0 or reps > 15:
        return None
    if reps == 1:
        return load_kg.quantize(_ONE_DECIMAL, rounding=ROUND_HALF_UP)
    estimate = load_kg * (Decimal("1") + (Decimal(reps) / Decimal("30")))
    return estimate.quantize(_ONE_DECIMAL, rounding=ROUND_HALF_UP)


def _exercise_personal_bests(
    rows: tuple[StrengthSetHistoryRow, ...],
) -> tuple[ExercisePersonalBest, ...]:
    grouped: dict[str, list[StrengthSetHistoryRow]] = {}
    for row in rows:
        grouped.setdefault(row.exercise_id, []).append(row)

    bests: list[ExercisePersonalBest] = []
    for exercise_id, exercise_rows in grouped.items():
        completed = tuple(row for row in exercise_rows if row.completed and not row.pain_flag)
        if not completed:
            continue
        loaded = tuple(
            row
            for row in completed
            if row.load_value_kg is not None and row.load_value_kg > 0
        )
        estimates_list: list[Decimal] = []
        for row in loaded:
            if row.load_value_kg is None or row.reps is None:
                continue
            estimate = estimate_epley_1rm(row.load_value_kg, row.reps)
            if estimate is not None:
                estimates_list.append(estimate)
        estimates = tuple(estimates_list)
        reps = tuple(row.reps for row in completed if row.reps is not None)
        bests.append(
            ExercisePersonalBest(
                exercise_id=exercise_id,
                display_name=display_name(exercise_id),
                sessions=len({row.event_id for row in completed}),
                best_load_kg=max(
                    (row.load_value_kg for row in loaded if row.load_value_kg is not None),
                    default=None,
                ),
                estimated_1rm_kg=max(estimates, default=None),
                best_reps=max(reps, default=None),
                last_performed_at=max(row.performed_at for row in completed),
            )
        )

    bests.sort(key=lambda item: (item.last_performed_at, item.display_name), reverse=True)
    return tuple(bests)


def _muscle_coverage(
    rows: tuple[StrengthSetHistoryRow, ...],
    anchor_day: date,
) -> tuple[MuscleCoverageRow, ...]:
    recent_cutoff = anchor_day - timedelta(days=13)
    exposure = {muscle: Decimal("0") for muscle in MUSCLE_ORDER}
    last_trained: dict[str, datetime | None] = {muscle: None for muscle in MUSCLE_ORDER}

    for row in rows:
        if not row.completed or row.pain_flag:
            continue
        profile = exercise_profile(row.exercise_id)
        muscles = tuple(dict.fromkeys((*profile.primary_muscles, *profile.secondary_muscles)))
        for muscle in muscles:
            if muscle not in exposure:
                continue
            previous = last_trained[muscle]
            if previous is None or row.performed_at > previous:
                last_trained[muscle] = row.performed_at
        if row.performed_at.date() < recent_cutoff or row.performed_at.date() > anchor_day:
            continue
        for muscle in profile.primary_muscles:
            if muscle in exposure:
                exposure[muscle] += _PRIMARY_SET_WEIGHT
        for muscle in profile.secondary_muscles:
            if muscle in exposure:
                exposure[muscle] += _SECONDARY_SET_WEIGHT

    maximum = max(exposure.values(), default=Decimal("0"))
    result: list[MuscleCoverageRow] = []
    for muscle in MUSCLE_ORDER:
        value = exposure[muscle].quantize(_ONE_DECIMAL)
        intensity = 0 if maximum <= 0 else round(float(value / maximum) * 100)
        result.append(
            MuscleCoverageRow(
                muscle_id=muscle,
                display_name=MUSCLE_LABELS[muscle],
                recent_set_equivalents=value,
                intensity_percent=intensity,
                last_trained_at=last_trained[muscle],
            )
        )
    return tuple(result)


def _activity_days(
    session: Session,
    person_id: str,
    rows: tuple[StrengthSetHistoryRow, ...],
    anchor_day: date,
) -> tuple[ActivityDay, ...]:
    workout_counts: dict[date, int] = {}
    for workout in get_workout_history(session, person_id):
        workout_day = workout.start_at.date()
        workout_counts[workout_day] = workout_counts.get(workout_day, 0) + 1

    set_counts: dict[date, int] = {}
    for row in rows:
        if not row.completed:
            continue
        set_day = row.performed_at.date()
        set_counts[set_day] = set_counts.get(set_day, 0) + 1

    first_day = anchor_day - timedelta(days=83)
    days: list[ActivityDay] = []
    for offset in range(84):
        current = first_day + timedelta(days=offset)
        workouts = workout_counts.get(current, 0)
        completed_sets = set_counts.get(current, 0)
        if workouts == 0 and completed_sets == 0:
            level = 0
        elif completed_sets >= 12:
            level = 4
        elif completed_sets >= 8:
            level = 3
        elif completed_sets >= 4:
            level = 2
        else:
            level = 1
        days.append(
            ActivityDay(
                day=current,
                workout_count=workouts,
                completed_sets=completed_sets,
                intensity_level=level,
            )
        )
    return tuple(days)


def get_training_analytics(
    session: Session,
    person_id: str,
    *,
    anchor_day: date | None = None,
) -> TrainingAnalytics:
    """Build read-only analytics for one resolved person."""

    day = anchor_day or datetime.now(UTC).date()
    rows = get_strength_set_history(session, person_id)
    return TrainingAnalytics(
        personal_bests=_exercise_personal_bests(rows),
        muscle_coverage=_muscle_coverage(rows, day),
        activity_days=_activity_days(session, person_id, rows, day),
    )
