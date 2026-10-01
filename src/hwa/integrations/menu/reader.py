"""Typed, fail-closed reader for Menu & Nutrition Health Export v3."""

from __future__ import annotations

from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError

from hwa.domain.identity import PersonContext

MENU_EXPORT_SCHEMA = "menu-nutrition.health-export"
MENU_EXPORT_VERSION = 3
MENU_SOURCE_AUTHORITY = "NUTRITION_APP"
MENU_TARGET_AUTHORITY = "menu_nutrition.profile_targets"
DEFAULT_HEALTH_EXPORT_URL = "http://homeassistant.local/api/menu_nutrition/health-export"


class MacroTargets(BaseModel):
    """Minimum macro target set consumed by Getfit."""

    model_config = ConfigDict(frozen=True)

    calories_kcal: float
    protein_g: float
    carbohydrate_g: float
    fat_g: float


class MenuNutritionDay(BaseModel):
    """Minimum per-day nutrition context required for presentation."""

    model_config = ConfigDict(frozen=True)

    date: str
    recorded_at: str
    atomic_evidence_id: str
    decision_eligible: bool
    logging_complete: bool
    logging_status: Literal["complete", "partial", "missing"]
    energy_consumed_kcal: float | None
    protein_g: float | None
    carbohydrate_g: float | None
    fat_g: float | None
    dietary_adherence: dict[str, Any]


class MenuNutritionContext(BaseModel):
    """Person-scoped nutrition context safe for Getfit consumption."""

    model_config = ConfigDict(frozen=True)

    status: Literal["READY", "UNAVAILABLE"]
    reason: str
    menu_person_id: str
    generated_at: str | None = None
    current_target: MacroTargets | None = None
    target_reason: str | None = None
    days: tuple[MenuNutritionDay, ...] = ()


class MenuNutritionReader:
    """Read Menu's authoritative Health Export without inheriting nutrition authority."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        endpoint_url: str = DEFAULT_HEALTH_EXPORT_URL,
    ) -> None:
        self._client = client
        self._endpoint_url = endpoint_url

    async def read(
        self,
        person: PersonContext,
        *,
        start: str | None = None,
        end: str | None = None,
    ) -> MenuNutritionContext:
        params: dict[str, str] = {"person_id": person.menu_person_id}
        if start:
            params["start"] = start
        if end:
            params["end"] = end

        try:
            response = await self._client.get(self._endpoint_url, params=params)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError, TypeError):
            return self._unavailable(person, "MENU_NUTRITION_UNAVAILABLE")

        if not isinstance(payload, dict):
            return self._unavailable(person, "INVALID_CONTRACT")
        if payload.get("schema") != MENU_EXPORT_SCHEMA or payload.get("schema_version") != 3:
            return self._unavailable(person, "CONTRACT_SCHEMA_MISMATCH")
        if payload.get("source_authority") != MENU_SOURCE_AUTHORITY:
            return self._unavailable(person, "SOURCE_AUTHORITY_MISMATCH")
        if payload.get("target_authority") != MENU_TARGET_AUTHORITY:
            return self._unavailable(person, "TARGET_AUTHORITY_MISMATCH")
        if payload.get("person_id") != person.menu_person_id:
            return self._unavailable(person, "PERSON_CONTEXT_MISMATCH")

        target, target_reason = self._project_target(payload.get("current_target"), person)
        days = self._project_days(payload.get("records"), person)
        if days is None:
            return self._unavailable(person, "INVALID_CONTRACT")

        generated_at = payload.get("generated_at")
        if generated_at is not None and not isinstance(generated_at, str):
            return self._unavailable(person, "INVALID_CONTRACT")

        return MenuNutritionContext(
            status="READY",
            reason="OK",
            menu_person_id=person.menu_person_id,
            generated_at=generated_at,
            current_target=target,
            target_reason=target_reason,
            days=days,
        )

    def _project_target(
        self,
        raw_target: object,
        person: PersonContext,
    ) -> tuple[MacroTargets | None, str | None]:
        if not isinstance(raw_target, dict):
            return None, "TARGET_CONTRACT_INVALID"
        if raw_target.get("authority") != MENU_TARGET_AUTHORITY:
            return None, "TARGET_AUTHORITY_MISMATCH"
        target_person = raw_target.get("person_id")
        if target_person is not None and target_person != person.menu_person_id:
            return None, "PERSON_CONTEXT_MISMATCH"
        status = raw_target.get("status")
        if status == "unavailable":
            reason = raw_target.get("reason")
            return None, str(reason or "TARGET_UNAVAILABLE")
        if status != "available":
            return None, "TARGET_CONTRACT_INVALID"
        targets = raw_target.get("targets")
        if not isinstance(targets, dict):
            return None, "TARGET_CONTRACT_INVALID"
        try:
            return (
                MacroTargets(
                    calories_kcal=targets["calories_kcal"],
                    protein_g=targets["protein_g"],
                    carbohydrate_g=targets["carbohydrates_g"],
                    fat_g=targets["fat_g"],
                ),
                None,
            )
        except (KeyError, ValidationError, TypeError, ValueError):
            return None, "TARGET_CONTRACT_INVALID"

    def _project_days(
        self,
        raw_records: object,
        person: PersonContext,
    ) -> tuple[MenuNutritionDay, ...] | None:
        if not isinstance(raw_records, list):
            return None
        output: list[MenuNutritionDay] = []
        for row in raw_records:
            if not isinstance(row, dict):
                return None
            if row.get("schema") != "menu-nutrition.health-day.v3":
                return None
            if row.get("schema_version") != MENU_EXPORT_VERSION:
                return None
            if row.get("source_authority") != MENU_SOURCE_AUTHORITY:
                return None
            if row.get("person_id") != person.menu_person_id:
                return None
            try:
                output.append(
                    MenuNutritionDay(
                        date=row["date"],
                        recorded_at=row["recorded_at"],
                        atomic_evidence_id=row["atomic_evidence_id"],
                        decision_eligible=row["decision_eligible"],
                        logging_complete=row["logging_complete"],
                        logging_status=row["nutrition_logging_status"],
                        energy_consumed_kcal=row.get("energy_consumed"),
                        protein_g=row.get("protein"),
                        carbohydrate_g=row.get("carbohydrate"),
                        fat_g=row.get("fat"),
                        dietary_adherence=dict(row.get("dietary_adherence") or {}),
                    )
                )
            except (KeyError, ValidationError, TypeError, ValueError):
                return None
        return tuple(output)

    @staticmethod
    def _unavailable(person: PersonContext, reason: str) -> MenuNutritionContext:
        return MenuNutritionContext(
            status="UNAVAILABLE",
            reason=reason,
            menu_person_id=person.menu_person_id,
        )
