"""Persistence models for mutable drafts and immutable workout evidence."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event as sa_event,
)
from sqlalchemy.orm import Mapped, mapped_column

from hwa.db.base import Base
from hwa.db.timestamp import UTCDateTime


class WorkoutDraft(Base):
    __tablename__ = "workout_drafts"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_workout_draft_version_positive"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    person_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("people.id", ondelete="CASCADE"), nullable=False
    )
    programme_day_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("programme_days.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    started_at_utc: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    updated_at_utc: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)


class WorkoutEvent(Base):
    """Stable logical workout identity whose effective revision can advance."""

    __tablename__ = "workout_events"
    __table_args__ = (
        CheckConstraint(
            "effective_revision_number > 0",
            name="ck_workout_event_effective_revision_positive",
        ),
    )

    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    person_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("people.id", ondelete="CASCADE"), nullable=False
    )
    programme_day_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("programme_days.id"), nullable=False
    )
    effective_revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at_utc: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)


class WorkoutRevision(Base):
    """Append-only canonical performed-workout revision."""

    __tablename__ = "workout_revisions"
    __table_args__ = (
        UniqueConstraint("event_id", "revision_number", name="uq_workout_event_revision"),
        CheckConstraint("revision_number > 0", name="ck_workout_revision_positive"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("workout_events.event_id"), nullable=False
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    supersedes_revision_number: Mapped[int | None] = mapped_column(Integer)
    canonical_json: Mapped[str] = mapped_column(Text, nullable=False)
    recorded_at_utc: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    correction_reason: Mapped[str | None] = mapped_column(Text)


class WorkoutIdempotencyKey(Base):
    """Durable command receipt used to replay duplicate submits safely."""

    __tablename__ = "workout_idempotency_keys"
    __table_args__ = (
        UniqueConstraint("person_id", "idempotency_key", name="uq_workout_person_idempotency"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    person_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("people.id", ondelete="CASCADE"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    command_type: Mapped[str] = mapped_column(String(16), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    event_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("workout_events.event_id"), nullable=False
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at_utc: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)


class ImmutableWorkoutRevisionError(RuntimeError):
    """Raised when code attempts to mutate append-only workout evidence."""


@sa_event.listens_for(WorkoutRevision, "before_update")
def _prevent_revision_update(
    mapper: Any,
    connection: Any,
    target: WorkoutRevision,
) -> None:
    del mapper, connection, target
    raise ImmutableWorkoutRevisionError("workout revisions are immutable")


@sa_event.listens_for(WorkoutRevision, "before_delete")
def _prevent_revision_delete(
    mapper: Any,
    connection: Any,
    target: WorkoutRevision,
) -> None:
    del mapper, connection, target
    raise ImmutableWorkoutRevisionError("workout revisions are immutable")
