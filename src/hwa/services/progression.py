"""Read-only progression evaluation from effective person-scoped workout evidence."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from hwa.db.models.workout import WorkoutEvent, WorkoutRevision
from hwa.domain.progression import (
    ProgressionDecision,
    ProgressionEvidence,
    ProgressionRule,
    decide_strength_progression,
)
from hwa.domain.workout import CanonicalWorkoutEventV1, TargetType


def _effective_events(
    session: Session,
    person_id: str,
) -> tuple[tuple[int, CanonicalWorkoutEventV1], ...]:
    logical_events = tuple(
        session.scalars(
            select(WorkoutEvent)
            .where(WorkoutEvent.person_id == person_id)
            .order_by(WorkoutEvent.created_at_utc.desc(), WorkoutEvent.event_id)
        ).all()
    )
    result: list[tuple[int, CanonicalWorkoutEventV1]] = []
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
        result.append((revision.revision_number, event))
    result.sort(key=lambda pair: pair[1].start_at, reverse=True)
    return tuple(result)


def _exercise_evidence(
    session: Session,
    person_id: str,
    exercise_id: str,
) -> tuple[ProgressionEvidence, ...]:
    evidence: list[ProgressionEvidence] = []
    for revision_number, event in _effective_events(session, person_id):
        for exercise in event.performance.strength:
            if exercise.exercise_id != exercise_id:
                continue
            reps = [
                set_item.reps
                for set_item in exercise.sets
                if set_item.target_type is TargetType.REPS and set_item.reps is not None
            ]
            rpe_values = [
                set_item.rpe for set_item in exercise.sets if set_item.rpe is not None
            ]
            rir_values = [
                set_item.rir for set_item in exercise.sets if set_item.rir is not None
            ]
            evidence.append(
                ProgressionEvidence(
                    person_id=person_id,
                    event_id=event.event_id,
                    revision_number=revision_number,
                    completed_sets=sum(1 for item in exercise.sets if item.completed),
                    total_sets=len(exercise.sets),
                    minimum_reps=min(reps) if reps else None,
                    maximum_rpe=max(rpe_values) if rpe_values else None,
                    minimum_rir=min(rir_values) if rir_values else None,
                    pain_flagged=any(item.pain_flag for item in exercise.sets),
                )
            )
    return tuple(evidence)


def evaluate_strength_progression(
    session: Session,
    *,
    person_id: str,
    exercise_id: str,
    current_load: Decimal | None,
    current_load_unit: str | None,
    rule: ProgressionRule | None,
) -> ProgressionDecision:
    """Evaluate progression without persisting any prescription or history mutation."""

    return decide_strength_progression(
        person_id=person_id,
        exercise_id=exercise_id,
        current_load=current_load,
        current_load_unit=current_load_unit,
        evidence=_exercise_evidence(session, person_id, exercise_id),
        rule=rule,
    )
