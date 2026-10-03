"""Pep WORKOUT_EVENT_SOURCE provider and trusted machine transport boundary."""

from __future__ import annotations

import hmac
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from hwa.api.dependencies import get_session
from hwa.integrations.pep.schemas import (
    PepWorkoutSourceExportV1,
    PepWorkoutSourceReadiness,
    PepWorkoutSourceRecordV1,
)
from hwa.integrations.pep.workout_export import export_workouts_for_pep
from hwa.repositories.identity import IdentityRepository


class PepWorkoutSourceProvider:
    """Match Pep's records(personId) + optional readiness(personId) provider interface."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def readiness(self, person_id: str) -> PepWorkoutSourceReadiness:
        pep_person_id = person_id.strip()
        if not pep_person_id:
            return PepWorkoutSourceReadiness(
                ready=False,
                state="UNAVAILABLE",
                reason="PERSON_ID_REQUIRED",
            )
        person = IdentityRepository(self._session).person_for_external_subject(
            "PEP_SITE", pep_person_id
        )
        if person is None or not person.active:
            return PepWorkoutSourceReadiness(
                ready=False,
                state="UNAVAILABLE",
                reason="PERSON_NOT_MAPPED",
            )
        return PepWorkoutSourceReadiness(ready=True, state="READY", reason="OK")

    def records(self, person_id: str) -> tuple[PepWorkoutSourceRecordV1, ...]:
        readiness = self.readiness(person_id)
        if not readiness.ready:
            return ()
        return export_workouts_for_pep(self._session, person_id)


router = APIRouter(prefix="/api/integrations/pep/v1", tags=["pep-integration"])


def _machine_credential(request: Request) -> str | None:
    raw = getattr(request.app.state, "pep_bridge_token", None)
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None


def require_pep_machine_auth(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """Require the separately configured Pep machine credential; ingress identity is irrelevant."""

    expected = _machine_credential(request)
    if expected is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "PEP_BRIDGE_NOT_CONFIGURED"},
        )
    scheme, _, supplied = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "PEP_BRIDGE_AUTH_REQUIRED"},
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.get(
    "/workouts/{person_id}",
    response_model=PepWorkoutSourceExportV1,
    dependencies=[Depends(require_pep_machine_auth)],
)
def pep_workout_machine_export(
    person_id: str,
    response: Response,
    session: Annotated[Session, Depends(get_session)],
) -> PepWorkoutSourceExportV1:
    """Return the effective read-only workout source for one explicit Pep person."""

    response.headers["Cache-Control"] = "no-store"
    provider = PepWorkoutSourceProvider(session)
    readiness = provider.readiness(person_id)
    records = provider.records(person_id) if readiness.ready else ()
    return PepWorkoutSourceExportV1(
        person_id=person_id.strip(),
        readiness=readiness,
        records=records,
    )
