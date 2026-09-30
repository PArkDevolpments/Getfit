"""Persistence model for mutable in-progress workout drafts."""

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text
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
