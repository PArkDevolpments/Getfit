"""Minimal Foundation browser workflow over the trusted workout API."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from hwa.api.dependencies import get_session, resolve_person_context
from hwa.db.models.programme import ProgrammeDay
from hwa.domain.identity import PersonContext
from hwa.services.workout_drafts import get_active_draft

router = APIRouter(tags=["foundation-web"])
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@router.get("/", response_class=HTMLResponse)
def foundation_home(
    request: Request,
    context: Annotated[PersonContext, Depends(resolve_person_context)],
    session: Annotated[Session, Depends(get_session)],
) -> HTMLResponse:
    """Render one person-scoped Week 1 Start/Resume surface."""

    days = tuple(
        session.scalars(
            select(ProgrammeDay)
            .where(
                ProgrammeDay.programme_id == "home-workout-12m-v1",
                ProgrammeDay.week_number == 1,
            )
            .order_by(ProgrammeDay.day_number)
        ).all()
    )
    active_draft = get_active_draft(session, context.hwa_person_id)

    if active_draft is not None:
        primary_action = "resume"
        primary_day = next(
            (day for day in days if day.id == active_draft.programme_day_id),
            None,
        )
    elif days:
        primary_action = "start"
        primary_day = days[0]
    else:
        primary_action = "unavailable"
        primary_day = None

    return templates.TemplateResponse(
        request=request,
        name="foundation.html",
        context={
            "person": context,
            "days": days,
            "active_draft": active_draft,
            "primary_action": primary_action,
            "primary_day": primary_day,
        },
    )
