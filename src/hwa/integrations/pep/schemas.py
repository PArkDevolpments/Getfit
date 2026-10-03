"""Versioned Getfit projection schema for Pep WORKOUT_EVENT_SOURCE."""

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from hwa.domain.workout import (
    HeartRateResponse,
    ProgrammeIdentity,
    TrainingLoad,
    WorkoutEffort,
    WorkoutPerformance,
)


class StrictPepExportModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class PepWorkoutProducerProvenance(StrictPepExportModel):
    authority: Literal["HOME_WORKOUT_ASSISTANT"] = "HOME_WORKOUT_ASSISTANT"
    source_instance: str = Field(min_length=1)
    recorded_at: AwareDatetime
    canonical_schema: Literal["home-workout-assistant.workout-event"] = (
        "home-workout-assistant.workout-event"
    )
    canonical_schema_version: Literal[1] = 1


class PepWorkoutSourceRecordV1(StrictPepExportModel):
    """One Pep provider row derived from one effective immutable workout revision."""

    schema_name: Literal["home-workout-assistant.pep-workout-source-record"] = Field(
        default="home-workout-assistant.pep-workout-source-record",
        alias="schema",
        serialization_alias="schema",
    )
    schema_version: Literal[1] = 1
    person_id: str = Field(min_length=1)
    hwa_person_id: str = Field(min_length=1)
    event_id: str = Field(min_length=1)
    source_event_id: str = Field(min_length=1)
    revision_number: int = Field(ge=1)
    supersedes_revision_number: int | None = Field(default=None, ge=1)
    start_at: AwareDatetime
    end_at: AwareDatetime
    duration: int = Field(ge=0)
    duration_unit: Literal["seconds"] = "seconds"
    workout_type: str = Field(min_length=1)
    programme: ProgrammeIdentity | None = None
    effort: WorkoutEffort
    heart_rate_response: HeartRateResponse
    training_load: TrainingLoad
    performance: WorkoutPerformance
    source_authority: Literal["WORKOUT_EVENT_SOURCE"] = "WORKOUT_EVENT_SOURCE"
    source_instance: str = Field(min_length=1)
    atomic_evidence_id: str = Field(min_length=1)
    recorded_at: AwareDatetime
    provenance: PepWorkoutProducerProvenance
    automatic_action: Literal[False] = False


class PepWorkoutSourceReadiness(StrictPepExportModel):
    ready: bool
    state: Literal["READY", "UNAVAILABLE"]
    reason: str = Field(min_length=1)
    source_authority: Literal["WORKOUT_EVENT_SOURCE"] = "WORKOUT_EVENT_SOURCE"


class PepWorkoutSourceExportV1(StrictPepExportModel):
    """Authenticated machine export envelope consumed by Pep Health."""

    schema_name: Literal["home-workout-assistant.pep-workout-export"] = Field(
        default="home-workout-assistant.pep-workout-export",
        alias="schema",
        serialization_alias="schema",
    )
    schema_version: Literal[1] = 1
    person_id: str = Field(min_length=1)
    readiness: PepWorkoutSourceReadiness
    records: tuple[PepWorkoutSourceRecordV1, ...]
    automatic_action: Literal[False] = False
