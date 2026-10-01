from __future__ import annotations

import importlib
from typing import Any

import httpx
import pytest

from hwa.domain.identity import PersonContext


def _context(
    *,
    pep_person_id: str = "person_a",
    health_profile_id: str = "kris",
) -> PersonContext:
    return PersonContext(
        hwa_person_id="hwa-kris",
        pep_person_id=pep_person_id,
        health_profile_id=health_profile_id,
        menu_person_id="person_1",
        presentation_profile="male",
        display_name="Kris",
    )


def _metric(
    metric: str,
    value: float | None,
    unit: str,
    *,
    status: str = "available",
    recorded_at: str | None = "2026-10-01T06:30:00Z",
    derived: bool = False,
    reason: str = "OK",
) -> dict[str, Any]:
    return {
        "status": status,
        "metric": metric,
        "value": value,
        "unit": unit,
        "recorded_at": recorded_at,
        "derived": derived,
        "reason": reason,
    }


def _ready_payload(
    *,
    person_id: str = "person_a",
    health_profile_id: str | None = "kris",
) -> dict[str, Any]:
    return {
        "schema": "peptide-site.health-context",
        "schema_version": 1,
        "authority": "PEPTIDE_SITE_HEALTH",
        "exported_at": "2026-10-01T06:35:00Z",
        "person_id": person_id,
        "health_profile_id": health_profile_id,
        "readiness": {
            "ready": True,
            "state": "READY",
            "reason": "OK",
            "usable_observation_count": 42,
            "data_quality": "GOOD",
        },
        "journey": {
            "status": "PROGRESS",
            "verdict": "JOURNEY_WORKING",
            "confidence": "HIGH",
            "reason": "POSITIVE_PROGRESS_EVIDENCE",
            "flags": ["BODY_RECOMPOSITION"],
        },
        "body": {
            "body_mass": _metric("body_mass", 113.7, "kg"),
            "height": _metric("height", 1.75, "m"),
            "body_fat_percentage": _metric("body_fat_percentage", 35.0, "%"),
            "lean_body_mass": _metric("lean_body_mass", 73.9, "kg"),
            "fat_mass": _metric("fat_mass", 39.8, "kg"),
            "waist_circumference": _metric(
                "waist_circumference",
                None,
                "cm",
                status="unavailable",
                recorded_at=None,
                reason="METRIC_UNAVAILABLE",
            ),
            "muscle_mass": _metric(
                "muscle_mass",
                None,
                "kg",
                status="unavailable",
                recorded_at=None,
                reason="METRIC_UNAVAILABLE",
            ),
            "bmi": _metric("bmi", 37.13, "kg/m²", derived=True, recorded_at=None),
        },
        "activity": {
            "steps": _metric("steps", 6500, "steps"),
            "exercise_time": _metric("exercise_time", 35, "min"),
            "active_calories": _metric("active_calories", 500, "kcal"),
            "distance": _metric("distance", 4800, "m"),
        },
        "recovery": {
            "resting_heart_rate": _metric("resting_heart_rate", 62, "bpm"),
            "heart_rate_variability": _metric("heart_rate_variability", 47, "ms"),
            "vo2_max": _metric("vo2_max", 34.5, "mL/kg/min"),
            "cardio_recovery": _metric("cardio_recovery", 25, "bpm"),
            "oxygen_saturation": _metric("oxygen_saturation", 98, "%"),
            "respiratory_rate": _metric("respiratory_rate", 14, "breaths/min"),
        },
        "sleep": {
            "sleep_duration": _metric("sleep_duration", 7.2, "h"),
            "sleep_core_hours": _metric("sleep_core_hours", 4.0, "h"),
            "sleep_rem_hours": _metric("sleep_rem_hours", 1.6, "h"),
            "sleep_deep_hours": _metric("sleep_deep_hours", 1.1, "h"),
            "sleep_awake_hours": _metric("sleep_awake_hours", 0.5, "h"),
        },
        "progress": {
            "semantics": "28_DAY_TREND_DERIVED",
            "fat_mass_change_28d_kg": -2.0,
            "waist_change_28d_cm": None,
            "ffm_change_28d_kg": -0.2,
            "total_weight_loss_28d_kg": 2.8,
            "ffm_loss_ratio_pct": 7.14,
            "body_recomposition": True,
            "confidence": "HIGH",
            "data_quality": "GOOD",
        },
        "domains": [
            {
                "domain_id": "weight",
                "state": "AVAILABLE",
                "reason": "AUTHORITATIVE_28D_WEIGHT_TREND_AVAILABLE",
                "ready": True,
                "decision_eligible": True,
            }
        ],
        "provenance": {
            "authority": "PEPTIDE_SITE_HEALTH",
            "runtime_version": "3",
        },
        "automatic_action": False,
        "causation_asserted": False,
    }


def _unavailable_payload() -> dict[str, Any]:
    payload = _ready_payload(person_id="person_b", health_profile_id=None)
    payload["readiness"] = {
        "ready": False,
        "state": "UNAVAILABLE",
        "reason": "HEALTH_PROFILE_NOT_MAPPED",
        "usable_observation_count": 0,
        "data_quality": "UNAVAILABLE",
    }
    for group in ("body", "activity", "recovery", "sleep"):
        for metric in payload[group].values():
            metric["status"] = "unavailable"
            metric["value"] = None
            metric["recorded_at"] = None
            metric["reason"] = "DATASET_NOT_READY"
    payload["journey"] = {
        "status": "UNKNOWN",
        "verdict": "HEALTH_JOURNEY_UNKNOWN",
        "confidence": "VERY_LOW",
        "reason": "HEALTH_PROFILE_NOT_MAPPED",
        "flags": [],
    }
    payload["domains"] = []
    return payload


def _module() -> Any:
    return importlib.import_module("hwa.integrations.pep.health_reader")


@pytest.mark.asyncio
async def test_ready_reader_uses_authenticated_transport_without_person_parameter() -> None:
    seen_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        return httpx.Response(200, json=_ready_payload())

    module = _module()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://ha.local"
    ) as client:
        result = await module.PepHealthReader(client).read(_context())

    assert len(seen_urls) == 1
    assert "person_id=" not in seen_urls[0]
    assert result.status == "READY"
    assert result.pep_person_id == "person_a"
    assert result.health_profile_id == "kris"
    assert result.source_state == "READY"
    assert result.data_quality == "GOOD"
    assert result.body["body_mass"].value == 113.7
    assert result.recovery["heart_rate_variability"].value == 47
    assert result.recovery["vo2_max"].value == 34.5
    assert result.sleep["sleep_duration"].value == 7.2
    assert result.progress is not None
    assert result.progress.total_weight_loss_28d_kg == 2.8
    assert result.runtime_version == "3"
    assert result.latest_recorded_at == "2026-10-01T06:30:00Z"


@pytest.mark.asyncio
async def test_unmapped_kirsty_fails_closed_without_metric_fallback() -> None:
    module = _module()

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_unavailable_payload())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await module.PepHealthReader(client).read(
            _context(pep_person_id="person_b", health_profile_id="kirsty")
        )

    assert result.status == "UNAVAILABLE"
    assert result.reason == "HEALTH_PROFILE_NOT_MAPPED"
    assert result.pep_person_id == "person_b"
    assert result.health_profile_id is None
    assert result.body == {}
    assert result.recovery == {}
    assert result.sleep == {}
    assert result.progress is None


@pytest.mark.asyncio
async def test_reader_rejects_cross_person_payload() -> None:
    module = _module()

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_ready_payload(person_id="person_b", health_profile_id="kirsty"))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await module.PepHealthReader(client).read(_context())

    assert result.status == "UNAVAILABLE"
    assert result.reason == "PERSON_CONTEXT_MISMATCH"


@pytest.mark.asyncio
async def test_reader_rejects_ready_health_profile_mismatch() -> None:
    module = _module()

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_ready_payload(health_profile_id="other"))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await module.PepHealthReader(client).read(_context())

    assert result.status == "UNAVAILABLE"
    assert result.reason == "HEALTH_PROFILE_MISMATCH"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema", "peptide-site.health-context.vNext"),
        ("schema_version", 2),
        ("authority", "OTHER_HEALTH"),
    ],
)
async def test_reader_fails_closed_on_contract_identity_drift(field: str, value: object) -> None:
    module = _module()
    payload = _ready_payload()
    payload[field] = value

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await module.PepHealthReader(client).read(_context())

    assert result.status == "UNAVAILABLE"
    assert result.reason == "CONTRACT_SCHEMA_MISMATCH"


@pytest.mark.asyncio
async def test_reader_rejects_sensitive_extra_fields() -> None:
    module = _module()
    payload = _ready_payload()
    payload["dose"] = {"compound": "must-never-enter-getfit"}

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await module.PepHealthReader(client).read(_context())

    assert result.status == "UNAVAILABLE"
    assert result.reason == "INVALID_CONTRACT"


@pytest.mark.asyncio
async def test_reader_preserves_pep_unavailable_state_without_smoothing() -> None:
    module = _module()
    payload = _ready_payload()
    payload["readiness"] = {
        "ready": False,
        "state": "UNAVAILABLE",
        "reason": "DATASET_STALE",
        "usable_observation_count": 8,
        "data_quality": "UNAVAILABLE",
    }

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await module.PepHealthReader(client).read(_context())

    assert result.status == "UNAVAILABLE"
    assert result.reason == "DATASET_STALE"
    assert result.source_state == "UNAVAILABLE"
    assert result.data_quality == "UNAVAILABLE"
    assert result.body == {}


@pytest.mark.asyncio
async def test_reader_degrades_on_transport_failure() -> None:
    module = _module()

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await module.PepHealthReader(client).read(_context())

    assert result.status == "UNAVAILABLE"
    assert result.reason == "PEP_HEALTH_UNAVAILABLE"
