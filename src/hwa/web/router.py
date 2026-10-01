"""Person-scoped Getfit product shell routes."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from hwa.api.dependencies import get_session, resolve_person_context
from hwa.db.models.programme import ProgrammeDay
from hwa.domain.identity import PersonContext
from hwa.services.workout_drafts import get_active_draft
from hwa.web.context import build_page_context

router = APIRouter(tags=["product-web"])
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

_IDENTITY_SELECTORS = frozenset(
    {
        "person_id",
        "hwa_person_id",
        "pep_person_id",
        "health_profile_id",
        "menu_person_id",
    }
)


def reject_identity_selectors(request: Request) -> None:
    """Reject browser attempts to choose identity instead of trusted ingress."""

    if _IDENTITY_SELECTORS.intersection(request.query_params):
        raise HTTPException(status_code=400, detail="IDENTITY_SELECTOR_NOT_ALLOWED")


def _surface_context(person: PersonContext, active_nav: str, title: str) -> dict[str, object]:
    return {
        "page": build_page_context(person, active_nav),
        "surface_title": title,
    }


@router.get("/", response_class=HTMLResponse, dependencies=[Depends(reject_identity_selectors)])
def today(
    request: Request,
    person: Annotated[PersonContext, Depends(resolve_person_context)],
    session: Annotated[Session, Depends(get_session)],
) -> HTMLResponse:
    """Render the product shell while preserving Foundation Start/Resume semantics."""

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
    active_draft = get_active_draft(session, person.hwa_person_id)
    if active_draft is not None:
        primary_action = "resume"
        primary_day = next((day for day in days if day.id == active_draft.programme_day_id), None)
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
            "page": build_page_context(person, "today"),
            "person": person,
            "days": days,
            "active_draft": active_draft,
            "primary_action": primary_action,
            "primary_day": primary_day,
        },
    )


def _render_surface(
    request: Request,
    person: PersonContext,
    *,
    active_nav: str,
    title: str,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="surface.html",
        context=_surface_context(person, active_nav, title),
    )


@router.get(
    "/workout",
    response_class=HTMLResponse,
    dependencies=[Depends(reject_identity_selectors)],
)
def workout(
    request: Request,
    person: Annotated[PersonContext, Depends(resolve_person_context)],
) -> HTMLResponse:
    return _render_surface(request, person, active_nav="workout", title="Workout")


@router.get(
    "/progress",
    response_class=HTMLResponse,
    dependencies=[Depends(reject_identity_selectors)],
)
def progress(
    request: Request,
    person: Annotated[PersonContext, Depends(resolve_person_context)],
) -> HTMLResponse:
    return _render_surface(request, person, active_nav="progress", title="Progress")


@router.get(
    "/library",
    response_class=HTMLResponse,
    dependencies=[Depends(reject_identity_selectors)],
)
def library(
    request: Request,
    person: Annotated[PersonContext, Depends(resolve_person_context)],
) -> HTMLResponse:
    return _render_surface(request, person, active_nav="library", title="Library")


@router.get(
    "/settings",
    response_class=HTMLResponse,
    dependencies=[Depends(reject_identity_selectors)],
)
def settings(
    request: Request,
    person: Annotated[PersonContext, Depends(resolve_person_context)],
) -> HTMLResponse:
    return _render_surface(request, person, active_nav="settings", title="Settings")
