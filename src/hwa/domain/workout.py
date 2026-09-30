"""Canonical structured workout evidence models."""

from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    """Base model for versioned HWA contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class LoadUnit(StrEnum):
    KG = "KG"


class LoadMode(StrEnum):
    EACH_HAND = "EACH_HAND"
    SINGLE_IMPLEMENT = "SINGLE_IMPLEMENT"
    TOTAL_EXTERNAL = "TOTAL_EXTERNAL"
    BODYWEIGHT = "BODYWEIGHT"
    ASSISTED = "ASSISTED"
    NONE = "NONE"


class TargetType(StrEnum):
    REPS = "REPS"
    DURATION = "DURATION"


class Laterality(StrEnum):
    BILATERAL = "BILATERAL"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    EACH_SIDE = "EACH_SIDE"


class Equipment(StrEnum):
    TREADMILL = "TREADMILL"
    SPIN_BIKE = "SPIN_BIKE"


class EvidenceStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


class StrengthSetEvidence(StrictModel):
    """One performed strength set, preserving how resistance was applied."""

    set_number: int = Field(ge=1)
    laterality: Laterality
    target_type: TargetType
    load_value: Decimal | None = Field(default=None, ge=0)
    load_unit: LoadUnit | None = None
    load_mode: LoadMode
    reps: int | None = Field(default=None, ge=0)
    duration_seconds: int | None = Field(default=None, gt=0)
    rir: int | None = Field(default=None, ge=0, le=5)
    rpe: Decimal | None = Field(default=None, ge=1, le=10)
    completed: bool
    pain_flag: bool

    @model_validator(mode="after")
    def validate_semantics(self) -> "StrengthSetEvidence":
        if self.target_type is TargetType.REPS:
            if self.reps is None or self.duration_seconds is not None:
                raise ValueError("REPS set requires reps and prohibits duration_seconds")
        elif self.duration_seconds is None or self.reps is not None:
            raise ValueError("DURATION set requires duration_seconds and prohibits reps")

        if self.load_mode in {LoadMode.BODYWEIGHT, LoadMode.NONE}:
            if self.load_value is not None or self.load_unit is not None:
                raise ValueError("BODYWEIGHT/NONE cannot contain an external load")
        elif self.load_value is not None and self.load_unit is None:
            raise ValueError("load_unit is required when load_value is recorded")
        return self


class StrengthExercisePerformance(StrictModel):
    """Performed evidence for one exercise."""

    exercise_id: str = Field(min_length=1)
    completed: bool
    sets: tuple[StrengthSetEvidence, ...]

    @model_validator(mode="after")
    def unique_set_sides(self) -> "StrengthExercisePerformance":
        identities = [(item.set_number, item.laterality) for item in self.sets]
        if len(identities) != len(set(identities)):
            raise ValueError("duplicate set number/laterality evidence")
        return self


class CardioPerformance(StrictModel):
    """Performed treadmill or spin-bike evidence with equipment-safe fields."""

    equipment: Equipment
    duration_seconds: int = Field(ge=0)
    speed_kmh: Decimal | None = Field(default=None, ge=0)
    incline_percent: Decimal | None = Field(default=None, ge=0)
    cadence_rpm_min: int | None = Field(default=None, ge=0)
    cadence_rpm_max: int | None = Field(default=None, ge=0)
    resistance: str | None = None
    rpe: Decimal | None = Field(default=None, ge=1, le=10)
    completed: bool

    @model_validator(mode="after")
    def validate_equipment_fields(self) -> "CardioPerformance":
        if self.equipment is Equipment.SPIN_BIKE:
            if self.speed_kmh is not None or self.incline_percent is not None:
                raise ValueError("spin bike cannot contain speed or incline")
        elif (
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
        return self


class HeartRateResponse(StrictModel):
    """Optional measured workout heart-rate response."""

    status: EvidenceStatus
    average_bpm: Decimal | None = Field(default=None, gt=0)
    maximum_bpm: Decimal | None = Field(default=None, gt=0)
    recovery_bpm: Decimal | None = Field(default=None, ge=0)
    source: str | None = None

    @model_validator(mode="after")
    def unavailable_is_empty(self) -> "HeartRateResponse":
        if self.status is EvidenceStatus.UNAVAILABLE and any(
            value is not None
            for value in (
                self.average_bpm,
                self.maximum_bpm,
                self.recovery_bpm,
                self.source,
            )
        ):
            raise ValueError("unavailable heart-rate evidence must remain empty")
        return self


class TrainingLoad(StrictModel):
    """Optional calculated training-load evidence."""

    status: EvidenceStatus
    method: str | None = None
    strength_volume_kg: Decimal | None = Field(default=None, ge=0)
    cardio_duration_seconds: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def unavailable_is_empty(self) -> "TrainingLoad":
        if self.status is EvidenceStatus.UNAVAILABLE and any(
            value is not None
            for value in (
                self.method,
                self.strength_volume_kg,
                self.cardio_duration_seconds,
            )
        ):
            raise ValueError("unavailable training-load evidence must remain empty")
        return self


class ProgrammeIdentity(StrictModel):
    programme_id: str = Field(min_length=1)
    programme_week: int = Field(ge=1)
    programme_day: int = Field(ge=1)
    block: str = Field(min_length=1)


class WorkoutEffort(StrictModel):
    session_rpe: Decimal | None = Field(default=None, ge=1, le=10)


class WorkoutPerformance(StrictModel):
    completed: bool
    strength: tuple[StrengthExercisePerformance, ...] = ()
    cardio: tuple[CardioPerformance, ...] = ()


class WorkoutProvenance(StrictModel):
    authority: Literal["HOME_WORKOUT_ASSISTANT"]
    source_instance: str = Field(min_length=1)
    recorded_at: AwareDatetime


class CanonicalWorkoutEventV1(StrictModel):
    """Versioned authoritative HWA workout read model."""

    schema_name: Literal["home-workout-assistant.workout-event"] = Field(
        default="home-workout-assistant.workout-event",
        alias="schema",
        serialization_alias="schema",
    )
    schema_version: Literal[1] = 1
    event_id: str = Field(min_length=1)
    source_event_id: str = Field(min_length=1)
    person_id: str = Field(min_length=1)
    start_at: AwareDatetime
    end_at: AwareDatetime
    duration_seconds: int = Field(ge=0)
    workout_type: str = Field(min_length=1)
    programme: ProgrammeIdentity | None = None
    effort: WorkoutEffort
    heart_rate_response: HeartRateResponse
    training_load: TrainingLoad
    performance: WorkoutPerformance
    provenance: WorkoutProvenance

    @model_validator(mode="after")
    def validate_timing(self) -> "CanonicalWorkoutEventV1":
        if self.end_at < self.start_at:
            raise ValueError("end_at cannot precede start_at")
        elapsed = (self.end_at - self.start_at).total_seconds()
        if elapsed != self.duration_seconds:
            raise ValueError("duration_seconds must match start_at/end_at")
        return self
