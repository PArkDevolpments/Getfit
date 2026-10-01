from __future__ import annotations

import importlib
from typing import Any

import httpx
import pytest

from hwa.domain.identity import PersonContext


def _context(menu_person_id: str = "person_1") -> PersonContext:
    return PersonContext(
        hwa_person_id="hwa-kris",
        pep_person_id="person_a",
        health_profile_id="kris",
        menu_person_id=menu_person_id,
        presentation_profile="male",
        display_name="Kris",
    )


def _payload(person_id: str = "person_1") -> dict[str, Any]:
    return {
        "schema": "menu-nutrition.health-export",
        "schema_version": 3,
        "source_authority": "NUTRITION_APP",
        "target_authority": "menu_nutrition.profile_targets",
        "person_id": person_id,
        "current_target": {
            "status": "available",
            "authority": "menu_nutrition.profile_targets",
            "person_id": person_id,
            "profile_id": "profile-1",
            "profile_name": "Kris",
            "plan_id": "plan-1",
            "captured_at": "2026-09-30T20:00:00Z",
            "source": "profile_targets",
            "immutable": False,
            "targets": {
                "calories_kcal": 2200,
                "protein_g": 180,
                "carbohydrates_g": 210,
                "fat_g": 70,
            },
        },
        "period_start": "2026-09-29",
        "period_end": "2026-09-30",
        "generated_at": "2026-09-30T20:05:00Z",
        "records": [
            {
                "schema": "menu-nutrition.health-day.v3",
                "schema_version": 3,
                "person_id": person_id,
                "date": "2026-09-30",
                "recorded_at": "2026-09-30T19:45:00Z",
                "source_authority": "NUTRITION_APP",
                "atomic_evidence_id": "nutrition-day-1",
                "exposure_basis": "actual",
                "decision_eligible": True,
                "logging_complete": True,
                "nutrition_logging_status": "complete",
                "target": {
                    "status": "available",
                    "authority": "menu_nutrition.profile_targets",
                    "person_id": person_id,
                    "targets": {
                        "calories_kcal": 2200,
                        "protein_g": 180,
                        "carbohydrates_g": 210,
                        "fat_g": 70,
                    },
                },
                "energy_consumed": 2050,
                "protein": 176,
                "carbohydrate": 198,
                "fat": 68,
                "fibre": 28,
                "water": 2400,
                "caffeine": 180,
                "meal_timing": [{"secret_meal_detail": "must-not-project"}],
                "dietary_adherence": {"calories": "within_target"},
                "planned": {"meals": ["private-plan-detail"]},
                "consumed": {"meals": ["private-consumption-detail"]},
                "source_event_ids": ["evt-1"],
            }
        ],
    }


def _module() -> Any:
    return importlib.import_module("hwa.integrations.menu.reader")


@pytest.mark.asyncio
async def test_reader_uses_server_resolved_menu_person_and_projects_minimum_context() -> None:
    seen_person_ids: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_person_ids.append(request.url.params.get("person_id", ""))
        return httpx.Response(200, json=_payload())

    module = _module()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://ha.local"
    ) as client:
        result = await module.MenuNutritionReader(client).read(_context())

    assert seen_person_ids == ["person_1"]
    assert result.status == "READY"
    assert result.menu_person_id == "person_1"
    assert result.current_target is not None
    assert result.current_target.calories_kcal == 2200
    assert result.current_target.protein_g == 180
    assert len(result.days) == 1
    assert result.days[0].energy_consumed_kcal == 2050
    assert result.days[0].protein_g == 176
    assert result.days[0].logging_status == "complete"
    serialized = result.model_dump(mode="json")
    assert "planned" not in serialized["days"][0]
    assert "consumed" not in serialized["days"][0]
    assert "meal_timing" not in serialized["days"][0]


@pytest.mark.asyncio
async def test_reader_fails_closed_on_cross_person_payload() -> None:
    module = _module()

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_payload("person_2"))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await module.MenuNutritionReader(client).read(_context("person_1"))

    assert result.status == "UNAVAILABLE"
    assert result.reason == "PERSON_CONTEXT_MISMATCH"
    assert result.current_target is None
    assert result.days == ()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("schema", "menu-nutrition.health-export.vNext", "CONTRACT_SCHEMA_MISMATCH"),
        ("schema_version", 4, "CONTRACT_SCHEMA_MISMATCH"),
        ("source_authority", "OTHER_APP", "SOURCE_AUTHORITY_MISMATCH"),
        ("target_authority", "other.targets", "TARGET_AUTHORITY_MISMATCH"),
    ],
)
async def test_reader_fails_closed_on_contract_drift(
    field: str, value: object, reason: str
) -> None:
    module = _module()
    payload = _payload()
    payload[field] = value

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await module.MenuNutritionReader(client).read(_context())

    assert result.status == "UNAVAILABLE"
    assert result.reason == reason


@pytest.mark.asyncio
async def test_reader_preserves_unavailable_target_without_inventing_macros() -> None:
    module = _module()
    payload = _payload()
    payload["current_target"] = {
        "status": "unavailable",
        "authority": "menu_nutrition.profile_targets",
        "person_id": "person_1",
        "targets": None,
        "reason": "PROFILE_TARGETS_UNAVAILABLE",
    }

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await module.MenuNutritionReader(client).read(_context())

    assert result.status == "READY"
    assert result.current_target is None
    assert result.target_reason == "PROFILE_TARGETS_UNAVAILABLE"


@pytest.mark.asyncio
async def test_reader_degrades_to_unavailable_on_transport_error() -> None:
    module = _module()

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await module.MenuNutritionReader(client).read(_context())

    assert result.status == "UNAVAILABLE"
    assert result.reason == "MENU_NUTRITION_UNAVAILABLE"
    assert result.days == ()
