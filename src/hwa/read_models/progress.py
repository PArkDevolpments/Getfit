"""Descriptive training Progress summaries derived from effective workout evidence."""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from hwa.db.models.programme import ProgrammeDay, ProgrammeDefinition
from hwa.read_models.history import (
    ExerciseHistoryRow,
    get_exercise_history,
    get_performed_exercise_ids,
    get_workout_history,
)


@dataclass(frozen=True, slots=True)
class ExerciseProgressSummary:
    exercise_id: str
    sessions: int
    latest_total_reps: int
    latest_total_duration_seconds: int
    latest_max_recorded_load_kg: object | None
    latest_completed_sets: int


@dataclass(frozen=True, slots=True)
class ProgressSummary:
    completed_workouts: int
    available_programme_workouts: int
    completion_percent: int
    latest_programme_week: int | None
    latest_programme_day: int | None
    exercise_summaries: tuple[ExerciseProgressSummary, ...]


def _programme_id(session: Session, person_id: str) -> str | None:
    history = get_workout_history(session, person_id)
    for row in history:
        if row.programme_id:
            return row.programme_id
    return session.scalar(
        select(ProgrammeDefinition.programme_id)
        .where(ProgrammeDefinition.active.is_(True))
        .order_by(ProgrammeDefinition.programme_id)
        .limit(1)
    )


def _latest_exercise_summary(
    exercise_id: str,
    history: tuple[ExerciseHistoryRow, ...],
) -> ExerciseProgressSummary:
    latest = history[0]
    return ExerciseProgressSummary(
        exercise_id=exercise_id,
        sessions=len(history),
        latest_total_reps=latest.total_reps,
        latest_total_duration_seconds=latest.total_duration_seconds,
        latest_max_recorded_load_kg=latest.max_recorded_load_kg,
        latest_completed_sets=latest.completed_sets,
    )


def get_progress_summary(session: Session, person_id: str) -> ProgressSummary:
    """Summarise only completed training evidence; no Health interpretation."""

    history = get_workout_history(session, person_id)
    programme_id = _programme_id(session, person_id)
    available = 0
    if programme_id is not None:
        available = int(
            session.scalar(
                select(func.count())
                .select_from(ProgrammeDay)
                .where(ProgrammeDay.programme_id == programme_id)
            )
            or 0
        )

    completed_positions = {
        (row.programme_week, row.programme_day)
        for row in history
        if row.programme_id == programme_id
        and row.programme_week is not None
        and row.programme_day is not None
    }
    completed = len(completed_positions)
    completion_percent = round((completed / available) * 100) if available else 0
    latest = history[0] if history else None

    exercise_summaries = tuple(
        _latest_exercise_summary(
            exercise_id,
            get_exercise_history(session, person_id, exercise_id),
        )
        for exercise_id in get_performed_exercise_ids(session, person_id)
    )
    return ProgressSummary(
        completed_workouts=completed,
        available_programme_workouts=available,
        completion_percent=completion_percent,
        latest_programme_week=latest.programme_week if latest else None,
        latest_programme_day=latest.programme_day if latest else None,
        exercise_summaries=exercise_summaries,
    )
