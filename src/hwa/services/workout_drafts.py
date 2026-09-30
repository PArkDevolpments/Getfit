"""Application service for mutable, resumable workout drafts."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from hwa.clock import to_utc
from hwa.db.models.workout import WorkoutDraft
from hwa.domain.draft import WorkoutDraftSnapshot


class DraftNotFoundError(LookupError):
    """Requested draft is not owned by the resolved person or does not exist."""


class DraftVersionConflict(RuntimeError):
    """Autosave expected an older server version than the current draft."""


@dataclass(frozen=True, slots=True)
class WorkoutDraftRecord:
    id: str
    person_id: str
    programme_day_id: str
    status: str
    version: int
    snapshot: WorkoutDraftSnapshot
    started_at: datetime
    updated_at: datetime


def _snapshot(value: WorkoutDraftSnapshot | dict[str, Any]) -> WorkoutDraftSnapshot:
    if isinstance(value, WorkoutDraftSnapshot):
        return value
    return WorkoutDraftSnapshot.model_validate(value)


def _record(row: WorkoutDraft) -> WorkoutDraftRecord:
    return WorkoutDraftRecord(
        id=row.id,
        person_id=row.person_id,
        programme_day_id=row.programme_day_id,
        status=row.status,
        version=row.version,
        snapshot=WorkoutDraftSnapshot.model_validate_json(row.snapshot_json),
        started_at=row.started_at_utc,
        updated_at=row.updated_at_utc,
    )


def create_draft(
    session: Session,
    *,
    person_id: str,
    programme_day_id: str,
    snapshot: WorkoutDraftSnapshot | dict[str, Any],
    started_at: datetime,
) -> WorkoutDraftRecord:
    """Create one active server-side workout draft."""

    started_utc = to_utc(started_at)
    parsed = _snapshot(snapshot)
    row = WorkoutDraft(
        id=str(uuid4()),
        person_id=person_id,
        programme_day_id=programme_day_id,
        status="ACTIVE",
        version=1,
        snapshot_json=parsed.model_dump_json(),
        started_at_utc=started_utc,
        updated_at_utc=started_utc,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _record(row)


def get_draft(
    session: Session,
    draft_id: str,
    person_id: str,
) -> WorkoutDraftRecord | None:
    """Return a draft only when it belongs to the resolved person."""

    row = session.scalar(
        select(WorkoutDraft).where(
            WorkoutDraft.id == draft_id,
            WorkoutDraft.person_id == person_id,
        )
    )
    return _record(row) if row is not None else None


def get_active_draft(session: Session, person_id: str) -> WorkoutDraftRecord | None:
    """Return the most recently updated active draft for one person."""

    row = session.scalar(
        select(WorkoutDraft)
        .where(
            WorkoutDraft.person_id == person_id,
            WorkoutDraft.status == "ACTIVE",
        )
        .order_by(WorkoutDraft.updated_at_utc.desc())
        .limit(1)
    )
    return _record(row) if row is not None else None


def autosave_draft(
    session: Session,
    *,
    draft_id: str,
    person_id: str,
    expected_version: int,
    snapshot: WorkoutDraftSnapshot | dict[str, Any],
    saved_at: datetime,
) -> WorkoutDraftRecord:
    """Atomically replace mutable draft state when the version token still matches."""

    if expected_version < 1:
        raise ValueError("expected_version must be positive")
    saved_utc = to_utc(saved_at)
    parsed = _snapshot(snapshot)

    current = session.scalar(
        select(WorkoutDraft).where(
            WorkoutDraft.id == draft_id,
            WorkoutDraft.person_id == person_id,
        )
    )
    if current is None:
        raise DraftNotFoundError(draft_id)
    if current.version != expected_version:
        raise DraftVersionConflict(
            f"draft version is {current.version}, expected {expected_version}"
        )
    if saved_utc < current.updated_at_utc:
        raise ValueError("saved_at cannot precede the current draft update")

    result = cast(
        CursorResult[Any],
        session.execute(
            update(WorkoutDraft)
            .where(
                WorkoutDraft.id == draft_id,
                WorkoutDraft.person_id == person_id,
                WorkoutDraft.version == expected_version,
            )
            .values(
                version=expected_version + 1,
                snapshot_json=parsed.model_dump_json(),
                updated_at_utc=saved_utc,
            )
        ),
    )
    if result.rowcount != 1:
        session.rollback()
        raise DraftVersionConflict("draft changed during autosave")

    session.commit()
    updated = session.scalar(
        select(WorkoutDraft).where(
            WorkoutDraft.id == draft_id,
            WorkoutDraft.person_id == person_id,
        )
    )
    if updated is None:
        raise DraftNotFoundError(draft_id)
    return _record(updated)
