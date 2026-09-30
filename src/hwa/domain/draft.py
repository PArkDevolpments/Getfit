"""Mutable in-progress workout state used for autosave and resume."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class DraftPhase(StrEnum):
    WORKOUT_READY = "WORKOUT_READY"
    EXERCISE_INTRO = "EXERCISE_INTRO"
    ACTIVE_SET = "ACTIVE_SET"
    SET_FEEDBACK = "SET_FEEDBACK"
    REST_TIMER = "REST_TIMER"
    NEXT_SET = "NEXT_SET"
    NEXT_EXERCISE = "NEXT_EXERCISE"
    CARDIO_COOLDOWN = "CARDIO_COOLDOWN"
    WORKOUT_SUMMARY = "WORKOUT_SUMMARY"


class WorkoutDraftSnapshot(BaseModel):
    """Server-authoritative cursor and transient entry state for one workout."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    phase: DraftPhase
    current_item_kind: Literal["STRENGTH", "CARDIO"] | None = None
    current_sequence: int | None = Field(default=None, ge=1)
    current_set_number: int | None = Field(default=None, ge=1)
    state_data: dict[str, JsonValue] = Field(default_factory=dict)
