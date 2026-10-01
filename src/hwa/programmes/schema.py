"""Strict document schema for approved programme week files."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from hwa.domain.programme import ProgrammeDayPrescription
from hwa.domain.workout import LoadMode, LoadUnit


class StrictProgrammeDocument(BaseModel):
    """Forbid silent schema expansion in approved programme files."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class PersonLoadOverrideDocument(StrictProgrammeDocument):
    day_number: int = Field(ge=1)
    exercise_id: str = Field(min_length=1)
    load_value: Decimal = Field(ge=0)
    load_unit: LoadUnit
    load_mode: LoadMode

    @model_validator(mode="after")
    def validate_external_load(self) -> "PersonLoadOverrideDocument":
        if self.load_mode in {LoadMode.BODYWEIGHT, LoadMode.NONE}:
            raise ValueError("person load override requires an external-load mode")
        return self


class ProgrammeWeekDocument(StrictProgrammeDocument):
    """One approved week of programme content; completeness is validated separately."""

    programme_id: str = Field(min_length=1)
    schema_version: int = Field(ge=1)
    week_number: int = Field(ge=1)
    days: tuple[ProgrammeDayPrescription, ...]
    person_overrides: dict[str, tuple[PersonLoadOverrideDocument, ...]] = {}
