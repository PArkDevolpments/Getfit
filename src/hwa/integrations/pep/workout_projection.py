"""Versioned HWA workout projection for Pep-Site's future authoritative provider binding."""

from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from hwa.domain.identity import PersonContext
from hwa.domain.workout import (
    HeartRateResponse,
    ProgrammeIdentity,
    TrainingLoad,
    WorkoutPerformance,
)
from hwa.services.workout_evidence import WorkoutRevisionRecord


class PepProjectionIdentityError(RuntimeError):
    """Projection attempted to cross person or logical-event boundaries."""


class PepProjectionProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_authority: Literal["HOME_WORKOUT_ASSISTANT"] = "HOME_WORKOUT_ASSISTANT"
    source_instance: str = Field(min_length=1)
    atomic_evidence_id: str = Field(min_length=1)
    recorded_at: AwareDatetime


class PepWorkoutProjectionV1(BaseModel):
    """Conservative HWA-owned read model prepared for Pep provider binding."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
    )

    schema_id: Literal["home-workout-assistant.pep-workout-projection"] = Field(
        default="home-workout-assistant.pep-workout-projection",
        alias="schema",
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
    duration_seconds: int = Field(ge=0)
    workout_type: str = Field(min_length=1)
    programme: ProgrammeIdentity | None = None
    session_rpe: Decimal | None = Field(default=None, ge=1, le=10)
    heart_rate_response: HeartRateResponse
    training_load: TrainingLoad
    performance: WorkoutPerformance
    provenance: PepProjectionProvenance


def project_workout_for_pep(
    context: PersonContext,
    revision: WorkoutRevisionRecord,
) -> PepWorkoutProjectionV1:
    """Project one immutable effective HWA revision without inventing Pep semantics."""

    event = revision.event
    if event.person_id != context.hwa_person_id:
        raise PepProjectionIdentityError("workout revision does not belong to person context")
    if event.event_id != revision.event_id:
        raise PepProjectionIdentityError("revision logical event identity is inconsistent")

    return PepWorkoutProjectionV1(
        person_id=context.pep_person_id,
        hwa_person_id=context.hwa_person_id,
        event_id=event.event_id,
        source_event_id=event.source_event_id,
        revision_number=revision.revision_number,
        supersedes_revision_number=revision.supersedes_revision_number,
        start_at=event.start_at,
        end_at=event.end_at,
        duration_seconds=event.duration_seconds,
        workout_type=event.workout_type,
        programme=event.programme,
        session_rpe=event.effort.session_rpe,
        heart_rate_response=event.heart_rate_response,
        training_load=event.training_load,
        performance=event.performance,
        provenance=PepProjectionProvenance(
            source_instance=event.provenance.source_instance,
            atomic_evidence_id=revision.revision_id,
            recorded_at=revision.recorded_at,
        ),
    )
