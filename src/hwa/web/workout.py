"""Guided workout player projection over approved programme and draft authority."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from hwa.db.models.identity import Person
from hwa.db.models.programme import (
    PersonPrescriptionOverride,
    ProgrammeCardioItem,
    ProgrammeDay,
    ProgrammeStrengthItem,
)
from hwa.domain.draft import WorkoutDraftSnapshot
from hwa.services.workout_drafts import DraftNotFoundError, get_draft


@dataclass(frozen=True, slots=True)
class StrengthTarget:
    item_id: str
    sequence: int
    exercise_id: str
    target_type: str
    sets_target: int
    reps_target: int | None
    reps_min: int | None
    reps_max: int | None
    duration_seconds_target: int | None
    duration_seconds_min: int | None
    duration_seconds_max: int | None
    laterality: str
    load_value: Decimal | None
    load_unit: str | None
    load_mode: str
    load_source: str
    rest_seconds_min: int | None
    rest_seconds_max: int | None
    tempo_eccentric_seconds: int | None
    tempo_concentric_seconds: int | None
    notes: str | None


@dataclass(frozen=True, slots=True)
class CardioTarget:
    item_id: str
    sequence: int
    equipment: str
    segment_type: str
    target_mode: str
    rounds: int | None
    duration_seconds: int | None
    speed_kmh: Decimal | None
    incline_percent: Decimal | None
    cadence_rpm_min: int | None
    cadence_rpm_max: int | None
    resistance: str | None
    rpe_min: Decimal | None
    rpe_max: Decimal | None


@dataclass(frozen=True, slots=True)
class WorkoutPlayerContext:
    display_name: str
    presentation_profile: str
    draft_id: str
    draft_version: int
    started_at: datetime
    snapshot: WorkoutDraftSnapshot
    programme_day_id: str
    week_number: int
    day_number: int
    title: str
    workout_type: str
    block: str
    strength: tuple[StrengthTarget, ...]
    cardio: tuple[CardioTarget, ...]


def _strength_targets(
    session: Session,
    person_id: str,
    programme_day_id: str,
) -> tuple[StrengthTarget, ...]:
    items = tuple(
        session.scalars(
            select(ProgrammeStrengthItem)
            .where(ProgrammeStrengthItem.programme_day_id == programme_day_id)
            .order_by(ProgrammeStrengthItem.sequence)
        ).all()
    )
    if not items:
        return ()

    overrides = {
        override.programme_strength_item_id: override
        for override in session.scalars(
            select(PersonPrescriptionOverride).where(
                PersonPrescriptionOverride.person_id == person_id,
                PersonPrescriptionOverride.programme_strength_item_id.in_(
                    [item.id for item in items]
                ),
            )
        ).all()
    }
    projected: list[StrengthTarget] = []
    for item in items:
        override = overrides.get(item.id)
        if override is not None:
            load_value = override.load_value
            load_unit = override.load_unit
            load_mode = override.load_mode or item.load_mode
            load_source = "PERSON_OVERRIDE"
        else:
            load_value = item.load_value
            load_unit = item.load_unit
            load_mode = item.load_mode
            load_source = "APPROVED_PROGRAMME"
        projected.append(
            StrengthTarget(
                item_id=item.id,
                sequence=item.sequence,
                exercise_id=item.exercise_id,
                target_type=item.target_type.upper(),
                sets_target=item.sets_target,
                reps_target=item.reps_target,
                reps_min=item.reps_min,
                reps_max=item.reps_max,
                duration_seconds_target=item.duration_seconds_target,
                duration_seconds_min=item.duration_seconds_min,
                duration_seconds_max=item.duration_seconds_max,
                laterality=item.laterality.upper(),
                load_value=load_value,
                load_unit=load_unit,
                load_mode=load_mode.upper(),
                load_source=load_source,
                rest_seconds_min=item.rest_seconds_min,
                rest_seconds_max=item.rest_seconds_max,
                tempo_eccentric_seconds=item.tempo_eccentric_seconds,
                tempo_concentric_seconds=item.tempo_concentric_seconds,
                notes=item.notes,
            )
        )
    return tuple(projected)


def get_strength_targets(
    session: Session,
    person_id: str,
    programme_day_id: str,
) -> tuple[StrengthTarget, ...]:
    """Project approved person-specific strength targets without requiring a draft."""

    return _strength_targets(session, person_id, programme_day_id)


def _cardio_targets(
    session: Session,
    programme_day_id: str,
) -> tuple[CardioTarget, ...]:
    items = tuple(
        session.scalars(
            select(ProgrammeCardioItem)
            .where(ProgrammeCardioItem.programme_day_id == programme_day_id)
            .order_by(ProgrammeCardioItem.sequence)
        ).all()
    )
    projected: list[CardioTarget] = []
    for item in items:
        equipment = item.equipment.upper()
        is_bike = equipment == "SPIN_BIKE"
        is_treadmill = equipment == "TREADMILL"
        projected.append(
            CardioTarget(
                item_id=item.id,
                sequence=item.sequence,
                equipment=equipment,
                segment_type=item.segment_type,
                target_mode=item.target_mode.upper(),
                rounds=item.rounds,
                duration_seconds=item.duration_seconds,
                speed_kmh=None if is_bike else item.speed_kmh,
                incline_percent=None if is_bike else item.incline_percent,
                cadence_rpm_min=None if is_treadmill else item.cadence_rpm_min,
                cadence_rpm_max=None if is_treadmill else item.cadence_rpm_max,
                resistance=None if is_treadmill else item.resistance,
                rpe_min=item.rpe_min,
                rpe_max=item.rpe_max,
            )
        )
    return tuple(projected)


def build_player_context(
    session: Session,
    person_id: str,
    draft_id: str,
) -> WorkoutPlayerContext:
    """Project one active person-owned draft and approved prescription for UI use."""

    draft = get_draft(session, draft_id, person_id)
    if draft is None:
        raise DraftNotFoundError(draft_id)
    person = session.get(Person, person_id)
    if person is None or not person.active:
        raise DraftNotFoundError(draft_id)
    day = session.get(ProgrammeDay, draft.programme_day_id)
    if day is None:
        raise DraftNotFoundError(draft_id)

    return WorkoutPlayerContext(
        display_name=person.display_name,
        presentation_profile=person.presentation_profile,
        draft_id=draft.id,
        draft_version=draft.version,
        started_at=draft.started_at,
        snapshot=draft.snapshot,
        programme_day_id=day.id,
        week_number=day.week_number,
        day_number=day.day_number,
        title=day.title,
        workout_type=day.workout_type,
        block=day.block,
        strength=_strength_targets(session, person_id, day.id),
        cardio=_cardio_targets(session, day.id),
    )
