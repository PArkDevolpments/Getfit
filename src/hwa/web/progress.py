"""Progress page projection over person-scoped training read models."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from hwa.read_models.history import WorkoutHistoryRow, get_workout_history
from hwa.read_models.progress import ProgressSummary, get_progress_summary


@dataclass(frozen=True, slots=True)
class ProgressPageContext:
    summary: ProgressSummary
    history: tuple[WorkoutHistoryRow, ...]


def build_progress_context(session: Session, person_id: str) -> ProgressPageContext:
    return ProgressPageContext(
        summary=get_progress_summary(session, person_id),
        history=get_workout_history(session, person_id),
    )
