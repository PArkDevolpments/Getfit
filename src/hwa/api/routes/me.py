"""Authenticated person identity route."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from hwa.api.dependencies import resolve_person_context
from hwa.domain.identity import PersonContext

router = APIRouter(prefix="/api/v1", tags=["identity"])


class MeResponse(BaseModel):
    """Stable cross-system identity visible to the authenticated person."""

    hwa_person_id: str
    pep_person_id: str
    health_profile_id: str
    menu_person_id: str
    presentation_profile: str
    display_name: str


@router.get("/me", response_model=MeResponse)
def me(
    context: Annotated[PersonContext, Depends(resolve_person_context)],
) -> MeResponse:
    """Return only the server-resolved identity for this request."""

    return MeResponse(
        hwa_person_id=context.hwa_person_id,
        pep_person_id=context.pep_person_id,
        health_profile_id=context.health_profile_id,
        menu_person_id=context.menu_person_id,
        presentation_profile=context.presentation_profile,
        display_name=context.display_name,
    )
