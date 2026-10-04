"""Deterministic read-only export for Pep WORKOUT_EVENT_SOURCE."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from hwa.db.models.workout import WorkoutEvent, WorkoutRevision
from hwa.domain.workout import CanonicalWorkoutEventV1
from hwa.integrations.pep.schemas import (
    PepWorkoutProducerProvenance,
    PepWorkoutSourceRecordV1,
)
from hwa.repositories.identity import IdentityRepository


class PepWorkoutExportIntegrityError(RuntimeError):
    """Effective workout evidence is internally inconsistent and cannot be exported."""


def _effective_revision(
    session: Session,
    logical: WorkoutEvent,
) -> WorkoutRevision:
    revision = session.scalar(
        select(WorkoutRevision).where(
            WorkoutRevision.event_id == logical.event_id,
            WorkoutRevision.revision_number == logical.effective_revision_number,
        )
    )
    if revision is None:
        raise PepWorkoutExportIntegrityError(
            f"effective revision is missing for workout {logical.event_id}"
        )
    return revision


def _project(
    *,
    pep_person_id: str,
    hwa_person_id: str,
    logical: WorkoutEvent,
    revision: WorkoutRevision,
) -> PepWorkoutSourceRecordV1 | None:
    event = CanonicalWorkoutEventV1.model_validate_json(revision.canonical_json)
    if event.event_id != logical.event_id:
        raise PepWorkoutExportIntegrityError("canonical event_id does not match logical workout")
    if event.person_id != hwa_person_id or logical.person_id != hwa_person_id:
        raise PepWorkoutExportIntegrityError("canonical workout crossed person identity")
    if revision.revision_number != logical.effective_revision_number:
        raise PepWorkoutExportIntegrityError("non-effective workout revision selected")
    if not event.performance.completed:
        return None

    return PepWorkoutSourceRecordV1(
        person_id=pep_person_id,
        hwa_person_id=hwa_person_id,
        event_id=event.event_id,
        source_event_id=event.source_event_id,
        revision_number=revision.revision_number,
        supersedes_revision_number=revision.supersedes_revision_number,
        start_at=event.start_at,
        end_at=event.end_at,
        duration=event.duration_seconds,
        workout_type=event.workout_type,
        programme=event.programme,
        effort=event.effort,
        heart_rate_response=event.heart_rate_response,
        training_load=event.training_load,
        performance=event.performance,
        source_instance=event.provenance.source_instance,
        atomic_evidence_id=revision.id,
        recorded_at=revision.recorded_at_utc,
        provenance=PepWorkoutProducerProvenance(
            source_instance=event.provenance.source_instance,
            recorded_at=event.provenance.recorded_at,
        ),
    )


def export_workouts_for_pep(
    session: Session,
    pep_person_id: str,
) -> tuple[PepWorkoutSourceRecordV1, ...]:
    """Return only effective completed workouts for one explicitly mapped Pep person."""

    pep_person_id = pep_person_id.strip()
    if not pep_person_id:
        return ()
    person = IdentityRepository(session).person_for_external_subject(
        "PEP_SITE", pep_person_id
    )
    if person is None or not person.active:
        return ()

    logical_events = tuple(
        session.scalars(
            select(WorkoutEvent)
            .where(WorkoutEvent.person_id == person.id)
            .order_by(WorkoutEvent.created_at_utc, WorkoutEvent.event_id)
        ).all()
    )
    rows: list[PepWorkoutSourceRecordV1] = []
    for logical in logical_events:
        revision = _effective_revision(session, logical)
        row = _project(
            pep_person_id=pep_person_id,
            hwa_person_id=person.id,
            logical=logical,
            revision=revision,
        )
        if row is not None:
            rows.append(row)

    rows.sort(key=lambda item: (item.start_at, item.event_id))
    return tuple(rows)


def workout_snapshot_generation_for_pep(
    session: Session,
    pep_person_id: str,
) -> int | None:
    """Return the monotonic append-only revision generation for one mapped Pep person."""

    pep_person_id = pep_person_id.strip()
    if not pep_person_id:
        return None
    person = IdentityRepository(session).person_for_external_subject(
        "PEP_SITE", pep_person_id
    )
    if person is None or not person.active:
        return None
    count = session.scalar(
        select(func.count(WorkoutRevision.id))
        .join(WorkoutEvent, WorkoutRevision.event_id == WorkoutEvent.event_id)
        .where(WorkoutEvent.person_id == person.id)
    )
    return int(count or 0)
