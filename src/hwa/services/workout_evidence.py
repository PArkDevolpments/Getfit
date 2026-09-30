"""Completion, correction, idempotency and effective workout evidence services."""

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from hwa.clock import to_utc
from hwa.db.models.programme import ProgrammeDay
from hwa.db.models.workout import (
    WorkoutDraft,
    WorkoutEvent,
    WorkoutIdempotencyKey,
    WorkoutRevision,
)
from hwa.domain.workout import CanonicalWorkoutEventV1


class WorkoutEvidenceNotFound(LookupError):
    """Requested workout evidence is absent or belongs to another person."""


class WorkoutEvidenceConflict(RuntimeError):
    """A logical workout identity conflicts with existing evidence."""


class IdempotencyConflict(RuntimeError):
    """An idempotency key was reused for a different command payload."""


@dataclass(frozen=True, slots=True)
class WorkoutRevisionRecord:
    revision_id: str
    event_id: str
    revision_number: int
    supersedes_revision_number: int | None
    event: CanonicalWorkoutEventV1
    recorded_at: datetime
    correction_reason: str | None


def _canonical_json(event: CanonicalWorkoutEventV1) -> str:
    return event.model_dump_json(by_alias=True)


def _request_hash(*parts: str) -> str:
    digest = sha256()
    for part in parts:
        digest.update(part.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def _receipt(
    session: Session,
    person_id: str,
    idempotency_key: str,
) -> WorkoutIdempotencyKey | None:
    return session.scalar(
        select(WorkoutIdempotencyKey).where(
            WorkoutIdempotencyKey.person_id == person_id,
            WorkoutIdempotencyKey.idempotency_key == idempotency_key,
        )
    )


def _revision_record(revision: WorkoutRevision) -> WorkoutRevisionRecord:
    return WorkoutRevisionRecord(
        revision_id=revision.id,
        event_id=revision.event_id,
        revision_number=revision.revision_number,
        supersedes_revision_number=revision.supersedes_revision_number,
        event=CanonicalWorkoutEventV1.model_validate_json(revision.canonical_json),
        recorded_at=revision.recorded_at_utc,
        correction_reason=revision.correction_reason,
    )


def _load_revision(
    session: Session,
    event_id: str,
    revision_number: int,
) -> WorkoutRevisionRecord:
    revision = session.scalar(
        select(WorkoutRevision).where(
            WorkoutRevision.event_id == event_id,
            WorkoutRevision.revision_number == revision_number,
        )
    )
    if revision is None:
        raise WorkoutEvidenceNotFound(event_id)
    return _revision_record(revision)


def _replay_receipt(
    session: Session,
    receipt: WorkoutIdempotencyKey,
    request_hash: str,
) -> WorkoutRevisionRecord:
    if receipt.request_hash != request_hash:
        raise IdempotencyConflict("idempotency key reused with a different request")
    return _load_revision(session, receipt.event_id, receipt.revision_number)


def _validate_event_matches_draft(
    session: Session,
    draft: WorkoutDraft,
    event: CanonicalWorkoutEventV1,
) -> None:
    if event.person_id != draft.person_id:
        raise WorkoutEvidenceNotFound(draft.id)
    programme = event.programme
    if programme is None:
        raise WorkoutEvidenceConflict("programme identity is required for Foundation workouts")
    day = session.get(ProgrammeDay, draft.programme_day_id)
    if day is None:
        raise WorkoutEvidenceConflict("draft programme day no longer exists")
    if (
        programme.programme_id != day.programme_id
        or programme.programme_week != day.week_number
        or programme.programme_day != day.day_number
        or programme.block != day.block
    ):
        raise WorkoutEvidenceConflict("performed event programme identity does not match draft")


def complete_workout(
    session: Session,
    *,
    person_id: str,
    draft_id: str,
    idempotency_key: str,
    event: CanonicalWorkoutEventV1,
    completed_at: datetime,
) -> WorkoutRevisionRecord:
    """Atomically close a draft and create immutable Revision 1."""

    if not idempotency_key.strip():
        raise ValueError("idempotency_key is required")
    completed_utc = to_utc(completed_at)
    canonical_json = _canonical_json(event)
    request_hash = _request_hash(
        "COMPLETE",
        draft_id,
        canonical_json,
        completed_utc.isoformat(),
    )

    existing_receipt = _receipt(session, person_id, idempotency_key)
    if existing_receipt is not None:
        return _replay_receipt(session, existing_receipt, request_hash)

    draft = session.scalar(
        select(WorkoutDraft).where(
            WorkoutDraft.id == draft_id,
            WorkoutDraft.person_id == person_id,
        )
    )
    if draft is None or draft.status != "ACTIVE":
        raise WorkoutEvidenceNotFound(draft_id)
    _validate_event_matches_draft(session, draft, event)

    if session.get(WorkoutEvent, event.event_id) is not None:
        raise WorkoutEvidenceConflict("logical event_id already exists")

    logical = WorkoutEvent(
        event_id=event.event_id,
        person_id=person_id,
        programme_day_id=draft.programme_day_id,
        effective_revision_number=1,
        created_at_utc=completed_utc,
    )
    session.add(logical)
    session.flush()

    revision = WorkoutRevision(
        id=str(uuid4()),
        event_id=event.event_id,
        revision_number=1,
        supersedes_revision_number=None,
        canonical_json=canonical_json,
        recorded_at_utc=completed_utc,
        correction_reason=None,
    )
    session.add(revision)
    session.add(
        WorkoutIdempotencyKey(
            id=str(uuid4()),
            person_id=person_id,
            idempotency_key=idempotency_key,
            command_type="COMPLETE",
            request_hash=request_hash,
            event_id=event.event_id,
            revision_number=1,
            created_at_utc=completed_utc,
        )
    )
    draft.status = "COMPLETED"
    draft.updated_at_utc = completed_utc
    session.commit()

    return _load_revision(session, event.event_id, 1)


def correct_workout(
    session: Session,
    *,
    person_id: str,
    event_id: str,
    idempotency_key: str,
    event: CanonicalWorkoutEventV1,
    reason: str,
    corrected_at: datetime,
) -> WorkoutRevisionRecord:
    """Append an immutable corrected revision and make it effective."""

    if not idempotency_key.strip():
        raise ValueError("idempotency_key is required")
    reason = reason.strip()
    if not reason:
        raise ValueError("correction reason is required")
    corrected_utc = to_utc(corrected_at)
    canonical_json = _canonical_json(event)
    request_hash = _request_hash(
        "CORRECT",
        event_id,
        canonical_json,
        reason,
        corrected_utc.isoformat(),
    )

    existing_receipt = _receipt(session, person_id, idempotency_key)
    if existing_receipt is not None:
        return _replay_receipt(session, existing_receipt, request_hash)

    logical = session.scalar(
        select(WorkoutEvent).where(
            WorkoutEvent.event_id == event_id,
            WorkoutEvent.person_id == person_id,
        )
    )
    if logical is None:
        raise WorkoutEvidenceNotFound(event_id)
    if event.event_id != event_id or event.person_id != person_id:
        raise WorkoutEvidenceConflict("correction must preserve logical event and person identity")

    previous_number = logical.effective_revision_number
    previous = session.scalar(
        select(WorkoutRevision).where(
            WorkoutRevision.event_id == event_id,
            WorkoutRevision.revision_number == previous_number,
        )
    )
    if previous is None:
        raise WorkoutEvidenceNotFound(event_id)

    revision_number = previous_number + 1
    revision = WorkoutRevision(
        id=str(uuid4()),
        event_id=event_id,
        revision_number=revision_number,
        supersedes_revision_number=previous_number,
        canonical_json=canonical_json,
        recorded_at_utc=corrected_utc,
        correction_reason=reason,
    )
    session.add(revision)
    session.add(
        WorkoutIdempotencyKey(
            id=str(uuid4()),
            person_id=person_id,
            idempotency_key=idempotency_key,
            command_type="CORRECT",
            request_hash=request_hash,
            event_id=event_id,
            revision_number=revision_number,
            created_at_utc=corrected_utc,
        )
    )
    logical.effective_revision_number = revision_number
    session.commit()

    return _load_revision(session, event_id, revision_number)


def get_effective_workout(
    session: Session,
    person_id: str,
    event_id: str,
) -> WorkoutRevisionRecord | None:
    """Return only the effective immutable revision for one resolved person."""

    logical = session.scalar(
        select(WorkoutEvent).where(
            WorkoutEvent.event_id == event_id,
            WorkoutEvent.person_id == person_id,
        )
    )
    if logical is None:
        return None
    return _load_revision(session, event_id, logical.effective_revision_number)
