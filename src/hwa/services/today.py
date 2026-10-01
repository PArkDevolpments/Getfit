"""Person-scoped Today/programme-position read model."""

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from hwa.db.models.programme import ProgrammeDay, ProgrammeDefinition
from hwa.db.models.workout import WorkoutEvent
from hwa.services.workout_drafts import get_active_draft

PrimaryAction = Literal["start", "resume", "programme_complete", "unavailable"]


@dataclass(frozen=True, slots=True)
class TodayView:
    """Trusted server-side programme position for one resolved person."""

    programme_id: str | None
    programme_title: str | None
    programme_day_id: str | None
    week_number: int | None
    day_number: int | None
    title: str | None
    workout_type: str | None
    block: str | None
    primary_action: PrimaryAction
    draft_id: str | None = None
    draft_version: int | None = None
    completed_day_count: int = 0
    available_day_count: int = 0


def _view_for_day(
    programme: ProgrammeDefinition,
    day: ProgrammeDay,
    *,
    action: PrimaryAction,
    completed_day_count: int,
    available_day_count: int,
    draft_id: str | None = None,
    draft_version: int | None = None,
) -> TodayView:
    return TodayView(
        programme_id=programme.programme_id,
        programme_title=programme.title,
        programme_day_id=day.id,
        week_number=day.week_number,
        day_number=day.day_number,
        title=day.title,
        workout_type=day.workout_type,
        block=day.block,
        primary_action=action,
        draft_id=draft_id,
        draft_version=draft_version,
        completed_day_count=completed_day_count,
        available_day_count=available_day_count,
    )


def _active_programme(session: Session) -> ProgrammeDefinition | None:
    return session.scalar(
        select(ProgrammeDefinition)
        .where(ProgrammeDefinition.active.is_(True))
        .order_by(ProgrammeDefinition.programme_id)
        .limit(1)
    )


def _programme_days(session: Session, programme_id: str) -> tuple[ProgrammeDay, ...]:
    return tuple(
        session.scalars(
            select(ProgrammeDay)
            .where(ProgrammeDay.programme_id == programme_id)
            .order_by(ProgrammeDay.week_number, ProgrammeDay.day_number)
        ).all()
    )


def _completed_day_ids(
    session: Session,
    person_id: str,
    days: tuple[ProgrammeDay, ...],
) -> set[str]:
    if not days:
        return set()
    return set(
        session.scalars(
            select(WorkoutEvent.programme_day_id).where(
                WorkoutEvent.person_id == person_id,
                WorkoutEvent.programme_day_id.in_([day.id for day in days]),
            )
        ).all()
    )


def get_today_view(session: Session, person_id: str) -> TodayView:
    """Resolve Today from approved content and person-scoped workout evidence.

    An active draft always wins. Otherwise the first imported approved day
    without a completed WorkoutEvent is next. Exhausting imported content
    reports programme_complete; this service never fabricates later weeks.
    """

    active_draft = get_active_draft(session, person_id)
    if active_draft is not None:
        day = session.get(ProgrammeDay, active_draft.programme_day_id)
        if day is not None:
            programme = session.get(ProgrammeDefinition, day.programme_id)
            if programme is not None and programme.active:
                days = _programme_days(session, programme.programme_id)
                completed_ids = _completed_day_ids(session, person_id, days)
                return _view_for_day(
                    programme,
                    day,
                    action="resume",
                    draft_id=active_draft.id,
                    draft_version=active_draft.version,
                    completed_day_count=len(completed_ids),
                    available_day_count=len(days),
                )

    programme = _active_programme(session)
    if programme is None:
        return TodayView(
            programme_id=None,
            programme_title=None,
            programme_day_id=None,
            week_number=None,
            day_number=None,
            title=None,
            workout_type=None,
            block=None,
            primary_action="unavailable",
        )

    days = _programme_days(session, programme.programme_id)
    if not days:
        return TodayView(
            programme_id=programme.programme_id,
            programme_title=programme.title,
            programme_day_id=None,
            week_number=None,
            day_number=None,
            title=None,
            workout_type=None,
            block=None,
            primary_action="unavailable",
        )

    completed_ids = _completed_day_ids(session, person_id, days)
    next_day = next((day for day in days if day.id not in completed_ids), None)
    if next_day is None:
        return TodayView(
            programme_id=programme.programme_id,
            programme_title=programme.title,
            programme_day_id=None,
            week_number=None,
            day_number=None,
            title=None,
            workout_type=None,
            block=None,
            primary_action="programme_complete",
            completed_day_count=len(completed_ids),
            available_day_count=len(days),
        )

    return _view_for_day(
        programme,
        next_day,
        action="start",
        completed_day_count=len(completed_ids),
        available_day_count=len(days),
    )
