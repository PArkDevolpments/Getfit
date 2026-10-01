"""Exercise Library read model derived only from canonical programme exercise IDs."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from hwa.db.models.programme import ProgrammeStrengthItem
from hwa.domain.exercise_media import ExerciseMedia, resolve_exercise_media


@dataclass(frozen=True, slots=True)
class ExerciseLibraryItem:
    exercise_id: str
    display_name: str
    media: ExerciseMedia


def display_name(exercise_id: str) -> str:
    return exercise_id.replace("-", " ").replace("_", " ").title()


def list_exercises(session: Session) -> tuple[ExerciseLibraryItem, ...]:
    exercise_ids = tuple(
        session.scalars(
            select(ProgrammeStrengthItem.exercise_id)
            .distinct()
            .order_by(ProgrammeStrengthItem.exercise_id)
        ).all()
    )
    return tuple(
        ExerciseLibraryItem(
            exercise_id=exercise_id,
            display_name=display_name(exercise_id),
            media=resolve_exercise_media(exercise_id),
        )
        for exercise_id in exercise_ids
    )


def get_exercise(session: Session, exercise_id: str) -> ExerciseLibraryItem | None:
    exists = session.scalar(
        select(ProgrammeStrengthItem.id)
        .where(ProgrammeStrengthItem.exercise_id == exercise_id)
        .limit(1)
    )
    if exists is None:
        return None
    return ExerciseLibraryItem(
        exercise_id=exercise_id,
        display_name=display_name(exercise_id),
        media=resolve_exercise_media(exercise_id),
    )
