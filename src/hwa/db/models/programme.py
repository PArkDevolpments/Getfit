"""Programme prescription persistence models."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from hwa.db.base import Base
from hwa.db.models.identity import utc_now
from hwa.db.timestamp import UTCDateTime


class ProgrammeDefinition(Base):
    __tablename__ = "programme_definitions"

    programme_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    seed_checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at_utc: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)


class ProgrammeDay(Base):
    __tablename__ = "programme_days"
    __table_args__ = (
        UniqueConstraint("programme_id", "week_number", "day_number", name="uq_programme_week_day"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    programme_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("programme_definitions.programme_id", ondelete="CASCADE"), nullable=False
    )
    week_number: Mapped[int] = mapped_column(Integer, nullable=False)
    day_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    workout_type: Mapped[str] = mapped_column(String(64), nullable=False)
    block: Mapped[str] = mapped_column(String(64), nullable=False)


class ProgrammeStrengthItem(Base):
    __tablename__ = "programme_strength_items"
    __table_args__ = (
        UniqueConstraint("programme_day_id", "sequence", name="uq_strength_day_sequence"),
        CheckConstraint("sets_target > 0", name="ck_strength_sets_positive"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    programme_day_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("programme_days.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    exercise_id: Mapped[str] = mapped_column(String(128), nullable=False)
    target_type: Mapped[str] = mapped_column(String(16), nullable=False)
    sets_target: Mapped[int] = mapped_column(Integer, nullable=False)
    reps_target: Mapped[int | None] = mapped_column(Integer)
    reps_min: Mapped[int | None] = mapped_column(Integer)
    reps_max: Mapped[int | None] = mapped_column(Integer)
    duration_seconds_target: Mapped[int | None] = mapped_column(Integer)
    duration_seconds_min: Mapped[int | None] = mapped_column(Integer)
    duration_seconds_max: Mapped[int | None] = mapped_column(Integer)
    laterality: Mapped[str] = mapped_column(String(16), nullable=False)
    load_value: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    load_unit: Mapped[str | None] = mapped_column(String(16))
    load_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    load_basis: Mapped[str | None] = mapped_column(String(64))
    rest_seconds_min: Mapped[int | None] = mapped_column(Integer)
    rest_seconds_max: Mapped[int | None] = mapped_column(Integer)
    tempo_eccentric_seconds: Mapped[int | None] = mapped_column(Integer)
    tempo_concentric_seconds: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)


class ProgrammeCardioItem(Base):
    __tablename__ = "programme_cardio_items"
    __table_args__ = (
        UniqueConstraint("programme_day_id", "sequence", name="uq_cardio_day_sequence"),
        CheckConstraint(
            "equipment != 'spin_bike' OR incline_percent IS NULL", name="ck_spin_bike_no_incline"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    programme_day_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("programme_days.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    equipment: Mapped[str] = mapped_column(String(32), nullable=False)
    segment_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    rounds: Mapped[int | None] = mapped_column(Integer)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    speed_kmh: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    incline_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    cadence_rpm_min: Mapped[int | None] = mapped_column(Integer)
    cadence_rpm_max: Mapped[int | None] = mapped_column(Integer)
    resistance: Mapped[str | None] = mapped_column(String(32))
    rpe_min: Mapped[Decimal | None] = mapped_column(Numeric(3, 1))
    rpe_max: Mapped[Decimal | None] = mapped_column(Numeric(3, 1))


class PersonProgrammeAssignment(Base):
    __tablename__ = "person_programme_assignments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    person_id: Mapped[str] = mapped_column(String(36), ForeignKey("people.id"), nullable=False)
    programme_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("programme_definitions.programme_id"), nullable=False
    )
    effective_from_utc: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    effective_to_utc: Mapped[datetime | None] = mapped_column(UTCDateTime())
    status: Mapped[str] = mapped_column(String(32), nullable=False)


class PersonPrescriptionOverride(Base):
    __tablename__ = "person_prescription_overrides"
    __table_args__ = (
        UniqueConstraint("person_id", "programme_strength_item_id", name="uq_person_strength_override"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    person_id: Mapped[str] = mapped_column(String(36), ForeignKey("people.id"), nullable=False)
    programme_strength_item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("programme_strength_items.id", ondelete="CASCADE"), nullable=False
    )
    load_value: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    load_unit: Mapped[str | None] = mapped_column(String(16))
    load_mode: Mapped[str | None] = mapped_column(String(32))
    created_at_utc: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
