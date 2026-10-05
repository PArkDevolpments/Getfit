"""Effective immutable workout history for one resolved person."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from hwa.db.models.workout import WorkoutEvent, WorkoutRevision
from hwa.domain.workout import CanonicalWorkoutEventV1, LoadUnit, TargetType


@dataclass(frozen=True, slots=True)
class WorkoutHistoryRow:
    event_id: str
    revision_number: int
    start_at: datetime
    end_at: datetime
    duration_seconds: int
    workout_type: str
    programme_id: str | None
    programme_week: int | None
    programme_day: int | None
    block: str | None
    session_rpe: Decimal | None
    completed: bool
    correction_reason: str | None


@dataclass(frozen=True, slots=True)
class ExerciseHistoryRow:
    event_id: str
    revision_number: int
    performed_at: datetime
    exercise_id: str
    completed: bool
    total_sets: int
    completed_sets: int
    total_reps: int
    total_duration_seconds: int
    max_recorded_load_kg: Decimal | None
    pain_flagged_sets: int


@dataclass(frozen=True, slots=True)
class StrengthSetHistoryRow:
    event_id: str
    revision_number: int
    performed_at: datetime
    exercise_id: str
    set_number: int
    laterality: str
    load_value_kg: Decimal | None
    load_mode: str
    reps: int | None
    duration_seconds: int | None
    rir: int | None
    rpe: Decimal | None
    completed: bool
    pain_flag: bool


@dataclass(frozen=True, slots=True)
class _EffectiveWorkout:
    event_id: str
    revision_number: int
    event: CanonicalWorkoutEventV1
    correction_reason: str | None


def _effective_workouts(
    session: Session,
    person_id: str,
) -> tuple[_EffectiveWorkout, ...]:
    logical_events = tuple(
        session.scalars(
            select(WorkoutEvent)
            .where(WorkoutEvent.person_id == person_id)
            .order_by(WorkoutEvent.created_at_utc.desc(), WorkoutEvent.event_id)
        ).all()
    )
    effective: list[_EffectiveWorkout] = []
    for logical in logical_events:
        revision = session.scalar(
            select(WorkoutRevision).where(
                WorkoutRevision.event_id == logical.event_id,
                WorkoutRevision.revision_number == logical.effective_revision_number,
            )
        )
        if revision is None:
            continue
        event = CanonicalWorkoutEventV1.model_validate_json(revision.canonical_json)
        if event.person_id != person_id or not event.performance.completed:
            continue
        effective.append(
            _EffectiveWorkout(
                event_id=logical.event_id,
                revision_number=revision.revision_number,
                event=event,
                correction_reason=revision.correction_reason,
            )
        )
    effective.sort(key=lambda item: item.event.start_at, reverse=True)
    return tuple(effective)


def get_workout_history(
    session: Session,
    person_id: str,
) -> tuple[WorkoutHistoryRow, ...]:
    """Return effective completed workouts only, newest first."""

    rows: list[WorkoutHistoryRow] = []
    for item in _effective_workouts(session, person_id):
        programme = item.event.programme
        rows.append(
            WorkoutHistoryRow(
                event_id=item.event_id,
                revision_number=item.revision_number,
                start_at=item.event.start_at,
                end_at=item.event.end_at,
                duration_seconds=item.event.duration_seconds,
                workout_type=item.event.workout_type,
                programme_id=programme.programme_id if programme else None,
                programme_week=programme.programme_week if programme else None,
                programme_day=programme.programme_day if programme else None,
                block=programme.block if programme else None,
                session_rpe=item.event.effort.session_rpe,
                completed=item.event.performance.completed,
                correction_reason=item.correction_reason,
            )
        )
    return tuple(rows)


def get_performed_exercise_ids(session: Session, person_id: str) -> tuple[str, ...]:
    exercise_ids = {
        exercise.exercise_id
        for item in _effective_workouts(session, person_id)
        for exercise in item.event.performance.strength
    }
    return tuple(sorted(exercise_ids))


def get_exercise_history(
    session: Session,
    person_id: str,
    exercise_id: str,
) -> tuple[ExerciseHistoryRow, ...]:
    """Return effective performed evidence for one canonical exercise."""

    rows: list[ExerciseHistoryRow] = []
    for item in _effective_workouts(session, person_id):
        for exercise in item.event.performance.strength:
            if exercise.exercise_id != exercise_id:
                continue
            completed_sets = sum(1 for set_item in exercise.sets if set_item.completed)
            total_reps = sum(
                set_item.reps or 0
                for set_item in exercise.sets
                if set_item.target_type is TargetType.REPS
            )
            total_duration_seconds = sum(
                set_item.duration_seconds or 0
                for set_item in exercise.sets
                if set_item.target_type is TargetType.DURATION
            )
            loads = [
                set_item.load_value
                for set_item in exercise.sets
                if set_item.load_value is not None and set_item.load_unit is LoadUnit.KG
            ]
            rows.append(
                ExerciseHistoryRow(
                    event_id=item.event_id,
                    revision_number=item.revision_number,
                    performed_at=item.event.start_at,
                    exercise_id=exercise.exercise_id,
                    completed=exercise.completed,
                    total_sets=len(exercise.sets),
                    completed_sets=completed_sets,
                    total_reps=total_reps,
                    total_duration_seconds=total_duration_seconds,
                    max_recorded_load_kg=max(loads) if loads else None,
                    pain_flagged_sets=sum(1 for set_item in exercise.sets if set_item.pain_flag),
                )
            )
    rows.sort(key=lambda row: row.performed_at, reverse=True)
    return tuple(rows)


def get_strength_set_history(
    session: Session,
    person_id: str,
    exercise_id: str | None = None,
) -> tuple[StrengthSetHistoryRow, ...]:
    """Return effective set-level strength evidence for descriptive analytics."""

    rows: list[StrengthSetHistoryRow] = []
    for item in _effective_workouts(session, person_id):
        for exercise in item.event.performance.strength:
            if exercise_id is not None and exercise.exercise_id != exercise_id:
                continue
            for set_item in exercise.sets:
                rows.append(
                    StrengthSetHistoryRow(
                        event_id=item.event_id,
                        revision_number=item.revision_number,
                        performed_at=item.event.start_at,
                        exercise_id=exercise.exercise_id,
                        set_number=set_item.set_number,
                        laterality=set_item.laterality.value,
                        load_value_kg=(
                            set_item.load_value
                            if set_item.load_unit is LoadUnit.KG
                            else None
                        ),
                        load_mode=set_item.load_mode.value,
                        reps=set_item.reps,
                        duration_seconds=set_item.duration_seconds,
                        rir=set_item.rir,
                        rpe=set_item.rpe,
                        completed=set_item.completed,
                        pain_flag=set_item.pain_flag,
                    )
                )
    rows.sort(
        key=lambda row: (row.performed_at, row.event_id, row.set_number),
        reverse=True,
    )
    return tuple(rows)


def get_weekly_cardio_minutes(
    session: Session,
    person_id: str,
    programme_id: str,
    week_number: int,
) -> int:
    """Return completed cardio minutes for one approved programme week."""

    seconds = 0
    for item in _effective_workouts(session, person_id):
        programme = item.event.programme
        if (
            programme is None
            or programme.programme_id != programme_id
            or programme.programme_week != week_number
        ):
            continue
        seconds += sum(
            cardio.duration_seconds
            for cardio in item.event.performance.cardio
            if cardio.completed
        )
    return seconds // 60
