"""Progress page projection over person-scoped training read models."""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from hwa.domain.exercise_catalog import display_name
from hwa.read_models.history import (
    ExerciseHistoryRow,
    WorkoutHistoryRow,
    get_exercise_history,
    get_workout_history,
)
from hwa.read_models.progress import ProgressSummary, get_progress_summary
from hwa.read_models.training_analytics import TrainingAnalytics, get_training_analytics


@dataclass(frozen=True, slots=True)
class ProgressChartPoint:
    label: str
    value: Decimal
    value_label: str
    x: int
    y: int


@dataclass(frozen=True, slots=True)
class ProgressChartSeries:
    exercise_id: str
    display_name: str
    metric_name: str
    points: tuple[ProgressChartPoint, ...]
    polyline: str
    min_label: str
    max_label: str


@dataclass(frozen=True, slots=True)
class ProgressPageContext:
    summary: ProgressSummary
    history: tuple[WorkoutHistoryRow, ...]
    chart: ProgressChartSeries | None
    analytics: TrainingAnalytics


def _chart_values(
    rows: tuple[ExerciseHistoryRow, ...],
) -> tuple[str, tuple[tuple[ExerciseHistoryRow, Decimal], ...]]:
    load_rows = tuple(
        (row, row.max_recorded_load_kg)
        for row in rows
        if row.max_recorded_load_kg is not None
    )
    if load_rows:
        return "Load (kg)", load_rows
    rep_rows = tuple((row, Decimal(row.total_reps)) for row in rows if row.total_reps > 0)
    return "Total reps", rep_rows


def _build_chart(
    session: Session,
    person_id: str,
    summary: ProgressSummary,
) -> ProgressChartSeries | None:
    exercise_ids = tuple(item.exercise_id for item in summary.exercise_summaries)
    if not exercise_ids:
        return None

    preferred = (
        "dumbbell_floor_press"
        if "dumbbell_floor_press" in exercise_ids
        else exercise_ids[0]
    )
    rows = get_exercise_history(session, person_id, preferred)
    metric_name, valued_rows = _chart_values(rows)
    if not valued_rows:
        return None

    chronological = tuple(reversed(valued_rows))
    values = [value for _, value in chronological]
    low = min(values)
    high = max(values)
    spread = high - low

    points: list[ProgressChartPoint] = []
    count = len(chronological)
    for index, (row, value) in enumerate(chronological):
        x = 50 if count == 1 else 50 + round((500 * index) / (count - 1))
        if spread == 0:
            y = 125
        else:
            y = 215 - round((150 * float(value - low)) / float(spread))
        suffix = " kg" if metric_name == "Load (kg)" else " reps"
        points.append(
            ProgressChartPoint(
                label=row.performed_at.strftime("%d %b"),
                value=value,
                value_label=f"{format(value.normalize(), 'f')}{suffix}",
                x=x,
                y=y,
            )
        )

    polyline = " ".join(f"{point.x},{point.y}" for point in points)
    suffix = " kg" if metric_name == "Load (kg)" else " reps"
    return ProgressChartSeries(
        exercise_id=preferred,
        display_name=display_name(preferred),
        metric_name=metric_name,
        points=tuple(points),
        polyline=polyline,
        min_label=f"{format(low.normalize(), 'f')}{suffix}",
        max_label=f"{format(high.normalize(), 'f')}{suffix}",
    )


def build_progress_context(session: Session, person_id: str) -> ProgressPageContext:
    summary = get_progress_summary(session, person_id)
    return ProgressPageContext(
        summary=summary,
        history=get_workout_history(session, person_id),
        chart=_build_chart(session, person_id, summary),
        analytics=get_training_analytics(session, person_id),
    )
