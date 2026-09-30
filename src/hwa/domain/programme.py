"""Canonical programme prescription models."""

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from hwa.domain.workout import Equipment, Laterality, LoadMode, LoadUnit, TargetType


class StrictProgrammeModel(BaseModel):
    """Base for programme prescription contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class TargetMode(StrEnum):
    FIXED = "FIXED"
    RANGE = "RANGE"
    CALIBRATION = "CALIBRATION"


class StrengthPrescription(StrictProgrammeModel):
    """One strength prescription item, separate from performed evidence."""

    sequence: int = Field(ge=1)
    exercise_id: str = Field(min_length=1)
    target_type: TargetType
    sets_target: int = Field(ge=1)
    reps_target: int | None = Field(default=None, ge=1)
    reps_min: int | None = Field(default=None, ge=1)
    reps_max: int | None = Field(default=None, ge=1)
    duration_seconds_target: int | None = Field(default=None, gt=0)
    duration_seconds_min: int | None = Field(default=None, gt=0)
    duration_seconds_max: int | None = Field(default=None, gt=0)
    laterality: Laterality
    load_value: Decimal | None = Field(default=None, ge=0)
    load_unit: LoadUnit | None = None
    load_mode: LoadMode
    load_basis: str | None = None
    rest_seconds_min: int | None = Field(default=None, ge=0)
    rest_seconds_max: int | None = Field(default=None, ge=0)
    tempo_eccentric_seconds: int | None = Field(default=None, ge=0)
    tempo_concentric_seconds: int | None = Field(default=None, ge=0)
    notes: str | None = None

    @model_validator(mode="after")
    def validate_target_and_load(self) -> "StrengthPrescription":
        reps_fields = (self.reps_target, self.reps_min, self.reps_max)
        duration_fields = (
            self.duration_seconds_target,
            self.duration_seconds_min,
            self.duration_seconds_max,
        )
        if self.target_type is TargetType.REPS:
            if not any(value is not None for value in reps_fields):
                raise ValueError("REPS prescription requires a repetition target")
            if any(value is not None for value in duration_fields):
                raise ValueError("REPS prescription cannot contain duration targets")
        else:
            if not any(value is not None for value in duration_fields):
                raise ValueError("DURATION prescription requires a duration target")
            if any(value is not None for value in reps_fields):
                raise ValueError("DURATION prescription cannot contain repetition targets")

        if self.reps_min is not None and self.reps_max is not None:
            if self.reps_min > self.reps_max:
                raise ValueError("reps_min cannot exceed reps_max")
        if (
            self.duration_seconds_min is not None
            and self.duration_seconds_max is not None
            and self.duration_seconds_min > self.duration_seconds_max
        ):
            raise ValueError("duration minimum cannot exceed maximum")
        if self.rest_seconds_min is not None and self.rest_seconds_max is not None:
            if self.rest_seconds_min > self.rest_seconds_max:
                raise ValueError("rest minimum cannot exceed maximum")

        if self.load_mode in {LoadMode.BODYWEIGHT, LoadMode.NONE}:
            if self.load_value is not None or self.load_unit is not None:
                raise ValueError("BODYWEIGHT/NONE cannot contain external load")
        elif self.load_value is not None and self.load_unit is None:
            raise ValueError("load_unit is required when load_value is prescribed")
        return self


class CardioPrescription(StrictProgrammeModel):
    """One treadmill or spin-bike prescription segment."""

    sequence: int = Field(ge=1)
    equipment: Equipment
    segment_type: str = Field(min_length=1)
    target_mode: TargetMode
    rounds: int | None = Field(default=None, ge=1)
    duration_seconds: int | None = Field(default=None, ge=0)
    speed_kmh: Decimal | None = Field(default=None, ge=0)
    incline_percent: Decimal | None = Field(default=None, ge=0)
    cadence_rpm_min: int | None = Field(default=None, ge=0)
    cadence_rpm_max: int | None = Field(default=None, ge=0)
    resistance: str | None = None
    rpe_min: Decimal | None = Field(default=None, ge=1, le=10)
    rpe_max: Decimal | None = Field(default=None, ge=1, le=10)
    notes: str | None = None

    @model_validator(mode="after")
    def validate_equipment_fields(self) -> "CardioPrescription":
        if self.equipment is Equipment.SPIN_BIKE:
            if self.speed_kmh is not None or self.incline_percent is not None:
                raise ValueError("spin bike cannot contain speed or incline")
        else:
            if (
                self.cadence_rpm_min is not None
                or self.cadence_rpm_max is not None
                or self.resistance is not None
            ):
                raise ValueError("treadmill cannot contain bike cadence/resistance")

        if (
            self.cadence_rpm_min is not None
            and self.cadence_rpm_max is not None
            and self.cadence_rpm_min > self.cadence_rpm_max
        ):
            raise ValueError("cadence minimum cannot exceed maximum")
        if self.rpe_min is not None and self.rpe_max is not None:
            if self.rpe_min > self.rpe_max:
                raise ValueError("rpe_min cannot exceed rpe_max")
        return self


class ProgrammeDayPrescription(StrictProgrammeModel):
    """Reusable data model for one programme day."""

    programme_id: str = Field(min_length=1)
    week_number: int = Field(ge=1)
    day_number: int = Field(ge=1)
    title: str = Field(min_length=1)
    workout_type: str = Field(min_length=1)
    block: str = Field(min_length=1)
    strength: tuple[StrengthPrescription, ...] = ()
    cardio: tuple[CardioPrescription, ...] = ()
