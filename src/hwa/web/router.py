"""Person-scoped Getfit product shell routes."""

from pathlib import Path
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from hwa.api.dependencies import get_session
from hwa.db.models.programme import ProgrammeDay
from hwa.domain.equipment import InstallationEquipmentProfile
from hwa.domain.external_context import ExternalContext, build_external_context
from hwa.domain.identity import PersonContext
from hwa.integrations.menu.reader import MenuNutritionContext, MenuNutritionReader
from hwa.integrations.pep.health_reader import PepHealthContext, PepHealthReader
from hwa.read_models.history import get_exercise_history
from hwa.services.today import get_today_view
from hwa.services.workout_drafts import get_active_draft
from hwa.web.context import build_page_context
from hwa.web.dependencies import resolve_web_person_context
from hwa.web.library import get_exercise, list_exercises
from hwa.web.progress import build_progress_context
from hwa.web.settings import build_settings_view
from hwa.web.urls import ingress_url
from hwa.web.workout import build_player_context

router = APIRouter(tags=["product-web"])
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.globals["ingress_url"] = ingress_url

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


async def _external_context(request: Request, person: PersonContext) -> ExternalContext:
    """Read optional external authorities independently and fail closed when unconfigured."""

    pep_reader = cast(PepHealthReader | None, request.app.state.pep_health_reader)
    menu_reader = cast(MenuNutritionReader | None, request.app.state.menu_nutrition_reader)

    pep = (
        await pep_reader.read(person)
        if pep_reader is not None
        else PepHealthContext(
            status="UNAVAILABLE",
            reason="PEP_HEALTH_NOT_CONFIGURED",
            pep_person_id=person.pep_person_id,
        )
    )
    menu = (
        await menu_reader.read(person)
        if menu_reader is not None
        else MenuNutritionContext(
            status="UNAVAILABLE",
            reason="MENU_NUTRITION_NOT_CONFIGURED",
            menu_person_id=person.menu_person_id,
        )
    )
    return build_external_context(pep, menu)


@router.get("/", response_class=HTMLResponse, dependencies=[Depends(reject_identity_selectors)])
async def today(
    request: Request,
    person: Annotated[PersonContext, Depends(resolve_web_person_context)],
    session: Annotated[Session, Depends(get_session)],
) -> HTMLResponse:
    """Render the trusted person-scoped Today programme position."""

    today_view = get_today_view(session, person.hwa_person_id)
    primary_day = (
        session.get(ProgrammeDay, today_view.programme_day_id)
        if today_view.programme_day_id
        else None
    )
    days: tuple[ProgrammeDay, ...] = ()
    if today_view.programme_id and today_view.week_number is not None:
        days = tuple(
            session.scalars(
                select(ProgrammeDay)
                .where(
                    ProgrammeDay.programme_id == today_view.programme_id,
                    ProgrammeDay.week_number == today_view.week_number,
                )
                .order_by(ProgrammeDay.day_number)
            ).all()
        )

    external_context = await _external_context(request, person)
    return templates.TemplateResponse(
        request=request,
        name="foundation.html",
        context={
            "page": build_page_context(person, "today"),
            "person": person,
            "days": days,
            "today_view": today_view,
            "primary_action": today_view.primary_action,
            "primary_day": primary_day,
            "external_context": external_context,
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
    person: Annotated[PersonContext, Depends(resolve_web_person_context)],
    session: Annotated[Session, Depends(get_session)],
) -> HTMLResponse:
    """Render only the resolved person's active server-owned workout draft."""

    active = get_active_draft(session, person.hwa_person_id)
    player = (
        build_player_context(session, person.hwa_person_id, active.id)
        if active is not None
        else None
    )
    return templates.TemplateResponse(
        request=request,
        name="workout.html",
        context={
            "page": build_page_context(person, "workout"),
            "person": person,
            "player": player,
        },
    )


@router.get(
    "/progress",
    response_class=HTMLResponse,
    dependencies=[Depends(reject_identity_selectors)],
)
def progress(
    request: Request,
    person: Annotated[PersonContext, Depends(resolve_web_person_context)],
    session: Annotated[Session, Depends(get_session)],
) -> HTMLResponse:
    """Render descriptive training progress for only the resolved person."""

    return templates.TemplateResponse(
        request=request,
        name="progress.html",
        context={
            "page": build_page_context(person, "progress"),
            "person": person,
            "progress": build_progress_context(session, person.hwa_person_id),
        },
    )


@router.get(
    "/library",
    response_class=HTMLResponse,
    dependencies=[Depends(reject_identity_selectors)],
)
def library(
    request: Request,
    person: Annotated[PersonContext, Depends(resolve_web_person_context)],
    session: Annotated[Session, Depends(get_session)],
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="library.html",
        context={
            "page": build_page_context(person, "library"),
            "person": person,
            "exercises": list_exercises(session),
        },
    )


@router.get(
    "/library/{exercise_id}",
    response_class=HTMLResponse,
    dependencies=[Depends(reject_identity_selectors)],
)
def exercise_detail(
    exercise_id: str,
    request: Request,
    person: Annotated[PersonContext, Depends(resolve_web_person_context)],
    session: Annotated[Session, Depends(get_session)],
) -> HTMLResponse:
    exercise = get_exercise(session, exercise_id)
    if exercise is None:
        raise HTTPException(status_code=404, detail="EXERCISE_NOT_FOUND")
    return templates.TemplateResponse(
        request=request,
        name="exercise_detail.html",
        context={
            "page": build_page_context(person, "library"),
            "person": person,
            "exercise": exercise,
            "exercise_history": get_exercise_history(\n                session, person.hwa_person_id, exercise_id\n            ),
        },
    )


@router.get(
    "/settings",
    response_class=HTMLResponse,
    dependencies=[Depends(reject_identity_selectors)],
)
def settings(
    request: Request,
    person: Annotated[PersonContext, Depends(resolve_web_person_context)],
) -> HTMLResponse:
    profile = cast(
        InstallationEquipmentProfile | None,
        request.app.state.equipment_profile,
    )
    settings_view = build_settings_view(
        person,
        profile,
        pep_health_configured=request.app.state.pep_health_reader is not None,
        menu_nutrition_configured=request.app.state.menu_nutrition_reader is not None,
    )
    return templates.TemplateResponse(
        request=request,
        name="settings.html",
        context={
            "page": build_page_context(person, "settings"),
            "person": person,
            "settings": settings_view,
        },
    )
