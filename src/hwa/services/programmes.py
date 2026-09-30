"""Validated programme seed loading and deterministic database import."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from hwa.db.models.identity import Person
from hwa.db.models.programme import (
    PersonPrescriptionOverride,
    ProgrammeCardioItem,
    ProgrammeDay,
    ProgrammeDefinition,
    ProgrammeStrengthItem,
)
from hwa.domain.programme import ProgrammeDayPrescription
from hwa.domain.workout import LoadMode, LoadUnit


class SeedModel(BaseModel):
    """Strict programme seed document base."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ProgrammeManifest(SeedModel):
    programme_id: str = Field(min_length=1)
    schema_version: int = Field(ge=1)
    title: str = Field(min_length=1)
    active: bool = True


class PersonLoadOverrideSeed(SeedModel):
    day_number: int = Field(ge=1)
    exercise_id: str = Field(min_length=1)
    load_value: Decimal = Field(ge=0)
    load_unit: LoadUnit
    load_mode: LoadMode


class WeekSeed(SeedModel):
    programme_id: str = Field(min_length=1)
    schema_version: int = Field(ge=1)
    week_number: int = Field(ge=1)
    days: tuple[ProgrammeDayPrescription, ...]
    person_overrides: dict[str, tuple[PersonLoadOverrideSeed, ...]] = {}

    @model_validator(mode="after")
    def validate_week_identity(self) -> "WeekSeed":
        if len(self.days) != len({day.day_number for day in self.days}):
            raise ValueError("week contains duplicate day numbers")
        for day in self.days:
            if day.programme_id != self.programme_id:
                raise ValueError("day programme_id does not match week")
            if day.week_number != self.week_number:
                raise ValueError("day week_number does not match week")
        return self


@dataclass(frozen=True, slots=True)
class SeedImportResult:
    changed: bool
    seed_checksum: str
    day_count: int
    strength_count: int
    cardio_count: int
    override_count: int


class SeedConflictError(RuntimeError):
    """Existing programme ID has different immutable seed evidence."""


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def load_programme_manifest(path: Path) -> ProgrammeManifest:
    return ProgrammeManifest.model_validate(_load_json(path))


def load_week_seed(path: Path) -> WeekSeed:
    return WeekSeed.model_validate(_load_json(path))


def _stable_id(*parts: object) -> str:
    return str(uuid5(NAMESPACE_URL, ":".join(str(part) for part in parts)))


def _checksum(manifest_path: Path, week_path: Path) -> str:
    digest = sha256()
    digest.update(manifest_path.read_bytes())
    digest.update(b"\0")
    digest.update(week_path.read_bytes())
    return digest.hexdigest()


def import_week_seed(
    session: Session,
    manifest_path: Path,
    week_path: Path,
) -> SeedImportResult:
    """Import one immutable programme/week seed or replay it without duplicates."""

    manifest = load_programme_manifest(manifest_path)
    week = load_week_seed(week_path)
    if manifest.programme_id != week.programme_id:
        raise ValueError("programme manifest and week seed do not match")
    if manifest.schema_version != week.schema_version:
        raise ValueError("programme manifest and week schema versions do not match")

    checksum = _checksum(manifest_path, week_path)
    existing = session.get(ProgrammeDefinition, manifest.programme_id)
    if existing is not None:
        if existing.seed_checksum != checksum:
            raise SeedConflictError(
                "programme seed changed without a new programme/version identity"
            )
        return SeedImportResult(False, checksum, 0, 0, 0, 0)

    programme = ProgrammeDefinition(
        programme_id=manifest.programme_id,
        schema_version=manifest.schema_version,
        title=manifest.title,
        active=manifest.active,
        seed_checksum=checksum,
        created_at_utc=datetime.now(UTC),
    )
    session.add(programme)

    strength_lookup: dict[tuple[int, str], ProgrammeStrengthItem] = {}
    strength_count = 0
    cardio_count = 0

    for day in week.days:
        day_id = _stable_id(manifest.programme_id, week.week_number, day.day_number)
        db_day = ProgrammeDay(
            id=day_id,
            programme_id=manifest.programme_id,
            week_number=week.week_number,
            day_number=day.day_number,
            title=day.title,
            workout_type=day.workout_type,
            block=day.block,
        )
        session.add(db_day)

        for strength_item in day.strength:
            item_id = _stable_id(
                day_id,
                "strength",
                strength_item.sequence,
                strength_item.exercise_id,
            )
            db_item = ProgrammeStrengthItem(
                id=item_id,
                programme_day_id=day_id,
                sequence=strength_item.sequence,
                exercise_id=strength_item.exercise_id,
                target_type=strength_item.target_type.value,
                sets_target=strength_item.sets_target,
                reps_target=strength_item.reps_target,
                reps_min=strength_item.reps_min,
                reps_max=strength_item.reps_max,
                duration_seconds_target=strength_item.duration_seconds_target,
                duration_seconds_min=strength_item.duration_seconds_min,
                duration_seconds_max=strength_item.duration_seconds_max,
                laterality=strength_item.laterality.value,
                load_value=strength_item.load_value,
                load_unit=(
                    strength_item.load_unit.value
                    if strength_item.load_unit is not None
                    else None
                ),
                load_mode=strength_item.load_mode.value,
                load_basis=strength_item.load_basis,
                rest_seconds_min=strength_item.rest_seconds_min,
                rest_seconds_max=strength_item.rest_seconds_max,
                tempo_eccentric_seconds=strength_item.tempo_eccentric_seconds,
                tempo_concentric_seconds=strength_item.tempo_concentric_seconds,
                notes=strength_item.notes,
            )
            session.add(db_item)
            strength_lookup[(day.day_number, strength_item.exercise_id)] = db_item
            strength_count += 1

        for cardio_item in day.cardio:
            item_id = _stable_id(
                day_id,
                "cardio",
                cardio_item.sequence,
                cardio_item.segment_type,
            )
            session.add(
                ProgrammeCardioItem(
                    id=item_id,
                    programme_day_id=day_id,
                    sequence=cardio_item.sequence,
                    equipment=cardio_item.equipment.value.lower(),
                    segment_type=cardio_item.segment_type,
                    target_mode=cardio_item.target_mode.value,
                    rounds=cardio_item.rounds,
                    duration_seconds=cardio_item.duration_seconds,
                    speed_kmh=cardio_item.speed_kmh,
                    incline_percent=cardio_item.incline_percent,
                    cadence_rpm_min=cardio_item.cadence_rpm_min,
                    cadence_rpm_max=cardio_item.cadence_rpm_max,
                    resistance=cardio_item.resistance,
                    rpe_min=cardio_item.rpe_min,
                    rpe_max=cardio_item.rpe_max,
                )
            )
            cardio_count += 1

    override_count = 0
    for canonical_key, overrides in week.person_overrides.items():
        person = session.scalar(select(Person).where(Person.canonical_key == canonical_key))
        if person is None:
            raise ValueError(f"programme override person is not configured: {canonical_key}")
        for override in overrides:
            strength = strength_lookup.get((override.day_number, override.exercise_id))
            if strength is None:
                raise ValueError(
                    "override references unknown strength item: "
                    f"day {override.day_number} {override.exercise_id}"
                )
            session.add(
                PersonPrescriptionOverride(
                    id=_stable_id(person.id, strength.id, "load-override"),
                    person_id=person.id,
                    programme_strength_item_id=strength.id,
                    load_value=override.load_value,
                    load_unit=override.load_unit.value,
                    load_mode=override.load_mode.value,
                    created_at_utc=datetime.now(UTC),
                )
            )
            override_count += 1

    session.commit()
    return SeedImportResult(
        True,
        checksum,
        len(week.days),
        strength_count,
        cardio_count,
        override_count,
    )
