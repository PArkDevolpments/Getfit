"""Exercise Library read model derived only from canonical programme exercise IDs."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from hwa.db.models.programme import ProgrammeStrengthItem
from hwa.domain.exercise_catalog import display_name as catalogue_display_name
from hwa.domain.exercise_catalog import exercise_profile
from hwa.domain.exercise_media import ExerciseMedia, resolve_exercise_media


@dataclass(frozen=True, slots=True)
class ExerciseLibraryItem:
    exercise_id: str
    display_name: str
    body_area: str
    movement_family: str
    technique_cues: tuple[str, ...]
    equipment: tuple[str, ...]
    primary_muscles: tuple[str, ...]
    secondary_muscles: tuple[str, ...]
    media: ExerciseMedia


def display_name(exercise_id: str) -> str:
    """Preserve the existing web helper while using the shared catalogue."""

    return catalogue_display_name(exercise_id)


def _item(exercise_id: str) -> ExerciseLibraryItem:
    profile = exercise_profile(exercise_id)
    return ExerciseLibraryItem(
        exercise_id=exercise_id,
        display_name=display_name(exercise_id),
        body_area=profile.body_area,
        movement_family=profile.movement_family,
        technique_cues=profile.technique_cues,
        equipment=profile.equipment,
        primary_muscles=profile.primary_muscles,
        secondary_muscles=profile.secondary_muscles,
        media=resolve_exercise_media(exercise_id),
    )


def list_exercises(session: Session) -> tuple[ExerciseLibraryItem, ...]:
    exercise_ids = tuple(
        session.scalars(
            select(ProgrammeStrengthItem.exercise_id)
            .distinct()
            .order_by(ProgrammeStrengthItem.exercise_id)
        ).all()
    )
    return tuple(_item(exercise_id) for exercise_id in exercise_ids)


def get_exercise(session: Session, exercise_id: str) -> ExerciseLibraryItem | None:
    exists = session.scalar(
        select(ProgrammeStrengthItem.id)
        .where(ProgrammeStrengthItem.exercise_id == exercise_id)
        .limit(1)
    )
    if exists is None:
        return None
    return _item(exercise_id)
