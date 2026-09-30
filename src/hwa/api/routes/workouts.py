"""Trusted person-scoped workout draft and evidence API."""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from hwa.api.dependencies import get_session, resolve_person_context
from hwa.db.models.workout import WorkoutIdempotencyKey
from hwa.domain.draft import WorkoutDraftSnapshot
from hwa.domain.identity import PersonContext
from hwa.domain.workout import CanonicalWorkoutEventV1
from hwa.services.workout_drafts import (
    DraftNotFoundError,
    DraftVersionConflict,
    WorkoutDraftRecord,
    autosave_draft,
    create_draft,
    get_active_draft,
)
from hwa.services.workout_evidence import (
    IdempotencyConflict,
    WorkoutEvidenceConflict,
    WorkoutEvidenceNotFound,
    WorkoutRevisionRecord,
    complete_workout,
    correct_workout,
    get_effective_workout,
)

router = APIRouter(prefix="/api/v1/workouts", tags=["workouts"])


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateDraftRequest(StrictRequest):
    programme_day_id: str = Field(min_length=1)
    snapshot: WorkoutDraftSnapshot
    started_at: AwareDatetime


class AutosaveDraftRequest(StrictRequest):
    expected_version: int = Field(ge=1)
    snapshot: WorkoutDraftSnapshot
    saved_at: AwareDatetime


class CompleteWorkoutRequest(StrictRequest):
    idempotency_key: str = Field(min_length=1)
    completed_at: AwareDatetime
    event: dict[str, Any]


class CorrectWorkoutRequest(StrictRequest):
    idempotency_key: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    corrected_at: AwareDatetime
    event: dict[str, Any]


class DraftResponse(BaseModel):
    draft_id: str
    programme_day_id: str
    status: str
    version: int
    snapshot: WorkoutDraftSnapshot
    started_at: datetime
    updated_at: datetime


class RevisionResponse(BaseModel):
    revision_id: str
    event_id: str
    revision_number: int
    supersedes_revision_number: int | None
    event: dict[str, Any]
    recorded_at: datetime
    correction_reason: str | None


def _draft_response(record: WorkoutDraftRecord) -> DraftResponse:
    return DraftResponse(
        draft_id=record.id,
        programme_day_id=record.programme_day_id,
        status=record.status,
        version=record.version,
        snapshot=record.snapshot,
        started_at=record.started_at,
        updated_at=record.updated_at,
    )


def _revision_response(record: WorkoutRevisionRecord) -> RevisionResponse:
    return RevisionResponse(
        revision_id=record.revision_id,
        event_id=record.event_id,
        revision_number=record.revision_number,
        supersedes_revision_number=record.supersedes_revision_number,
        event=record.event.model_dump(mode="json", by_alias=True),
        recorded_at=record.recorded_at,
        correction_reason=record.correction_reason,
    )


def _canonical_event(
    payload: dict[str, Any],
    context: PersonContext,
) -> CanonicalWorkoutEventV1:
    if "person_id" in payload:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "PERSON_ID_SERVER_DERIVED"},
        )
    trusted_payload = dict(payload)
    trusted_payload["person_id"] = context.hwa_person_id
    try:
        return CanonicalWorkoutEventV1.model_validate(trusted_payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "INVALID_WORKOUT_EVENT", "errors": exc.errors()},
        ) from exc


def _has_receipt(
    session: Session,
    person_id: str,
    idempotency_key: str,
) -> bool:
    return (
        session.scalar(
            select(WorkoutIdempotencyKey.id).where(
                WorkoutIdempotencyKey.person_id == person_id,
                WorkoutIdempotencyKey.idempotency_key == idempotency_key,
            )
        )
        is not None
    )


def _evidence_error(exc: Exception) -> HTTPException:
    if isinstance(exc, WorkoutEvidenceNotFound):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "WORKOUT_NOT_FOUND"},
        )
    if isinstance(exc, IdempotencyConflict):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "IDEMPOTENCY_CONFLICT"},
        )
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": "WORKOUT_EVIDENCE_CONFLICT"},
    )


@router.post("/drafts", response_model=DraftResponse, status_code=status.HTTP_201_CREATED)
def start_draft(
    body: CreateDraftRequest,
    context: Annotated[PersonContext, Depends(resolve_person_context)],
    session: Annotated[Session, Depends(get_session)],
) -> DraftResponse:
    record = create_draft(
        session,
        person_id=context.hwa_person_id,
        programme_day_id=body.programme_day_id,
        snapshot=body.snapshot,
        started_at=body.started_at,
    )
    return _draft_response(record)


@router.get("/drafts/active", response_model=DraftResponse)
def active_draft(
    context: Annotated[PersonContext, Depends(resolve_person_context)],
    session: Annotated[Session, Depends(get_session)],
) -> DraftResponse:
    record = get_active_draft(session, context.hwa_person_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ACTIVE_DRAFT_NOT_FOUND"},
        )
    return _draft_response(record)


@router.put("/drafts/{draft_id}", response_model=DraftResponse)
def save_draft(
    draft_id: str,
    body: AutosaveDraftRequest,
    context: Annotated[PersonContext, Depends(resolve_person_context)],
    session: Annotated[Session, Depends(get_session)],
) -> DraftResponse:
    try:
        record = autosave_draft(
            session,
            draft_id=draft_id,
            person_id=context.hwa_person_id,
            expected_version=body.expected_version,
            snapshot=body.snapshot,
            saved_at=body.saved_at,
        )
    except DraftNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "DRAFT_NOT_FOUND"},
        ) from exc
    except DraftVersionConflict as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DRAFT_VERSION_CONFLICT"},
        ) from exc
    return _draft_response(record)


@router.post(
    "/drafts/{draft_id}/complete",
    response_model=RevisionResponse,
    status_code=status.HTTP_201_CREATED,
)
def complete_draft(
    draft_id: str,
    body: CompleteWorkoutRequest,
    response: Response,
    context: Annotated[PersonContext, Depends(resolve_person_context)],
    session: Annotated[Session, Depends(get_session)],
) -> RevisionResponse:
    replay = _has_receipt(session, context.hwa_person_id, body.idempotency_key)
    event = _canonical_event(body.event, context)
    try:
        record = complete_workout(
            session,
            person_id=context.hwa_person_id,
            draft_id=draft_id,
            idempotency_key=body.idempotency_key,
            event=event,
            completed_at=body.completed_at,
        )
    except (WorkoutEvidenceNotFound, WorkoutEvidenceConflict, IdempotencyConflict) as exc:
        raise _evidence_error(exc) from exc
    if replay:
        response.status_code = status.HTTP_200_OK
    return _revision_response(record)


@router.get("/{event_id}", response_model=RevisionResponse)
def effective_workout(
    event_id: str,
    context: Annotated[PersonContext, Depends(resolve_person_context)],
    session: Annotated[Session, Depends(get_session)],
) -> RevisionResponse:
    record = get_effective_workout(session, context.hwa_person_id, event_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "WORKOUT_NOT_FOUND"},
        )
    return _revision_response(record)


@router.post(
    "/{event_id}/corrections",
    response_model=RevisionResponse,
    status_code=status.HTTP_201_CREATED,
)
def correct_effective_workout(
    event_id: str,
    body: CorrectWorkoutRequest,
    response: Response,
    context: Annotated[PersonContext, Depends(resolve_person_context)],
    session: Annotated[Session, Depends(get_session)],
) -> RevisionResponse:
    replay = _has_receipt(session, context.hwa_person_id, body.idempotency_key)
    event = _canonical_event(body.event, context)
    try:
        record = correct_workout(
            session,
            person_id=context.hwa_person_id,
            event_id=event_id,
            idempotency_key=body.idempotency_key,
            event=event,
            reason=body.reason,
            corrected_at=body.corrected_at,
        )
    except (WorkoutEvidenceNotFound, WorkoutEvidenceConflict, IdempotencyConflict) as exc:
        raise _evidence_error(exc) from exc
    if replay:
        response.status_code = status.HTTP_200_OK
    return _revision_response(record)
