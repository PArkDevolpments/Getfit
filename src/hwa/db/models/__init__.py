"""ORM model registration."""

from hwa.db.models.identity import ExternalIdentityMapping, Person
from hwa.db.models.programme import (
    PersonPrescriptionOverride,
    PersonProgrammeAssignment,
    ProgrammeCardioItem,
    ProgrammeDay,
    ProgrammeDefinition,
    ProgrammeStrengthItem,
)
from hwa.db.models.workout import (
    WorkoutDraft,
    WorkoutEvent,
    WorkoutIdempotencyKey,
    WorkoutRevision,
)

__all__ = [
    "ExternalIdentityMapping",
    "Person",
    "PersonPrescriptionOverride",
    "PersonProgrammeAssignment",
    "ProgrammeCardioItem",
    "ProgrammeDay",
    "ProgrammeDefinition",
    "ProgrammeStrengthItem",
    "WorkoutDraft",
    "WorkoutEvent",
    "WorkoutIdempotencyKey",
    "WorkoutRevision",
]
