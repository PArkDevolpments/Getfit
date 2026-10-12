from __future__ import annotations

import asyncio
import importlib
from typing import Any

import pytest

from hwa.domain.identity import PersonContext
from hwa.integrations.pep.ha_health_service import HaHealthServiceEnvelope, HaHealthServiceFailure


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


class _Signer:
    def __init__(self) -> None:
        self.subjects: list[str] = []

    def sign(self, subject: str) -> str:
        self.subjects.append(subject)
        return f"synthetic-assertion-{len(self.subjects)}"


class _Service:
    def __init__(self, result: HaHealthServiceEnvelope | HaHealthServiceFailure) -> None:
        self.result = result
        self.assertions: list[str] = []

    async def get_health_context(
        self, assertion: str
    ) -> HaHealthServiceEnvelope | HaHealthServiceFailure:
        self.assertions.append(assertion)
        return self.result


async def _read(payload: dict[str, Any], person: PersonContext | None = None) -> Any:
    service = _Service(HaHealthServiceEnvelope(200, payload, {"Cache-Control": "no-store"}))
    reader = _module().PepHealthReader(service_client=service, signer=_Signer())
    return await reader.read(ha_user_id="synthetic-ha-subject", person=person or _context())


@pytest.mark.asyncio
async def test_ready_reader_uses_authenticated_transport_without_person_parameter() -> None:
    signer = _Signer()
    service = _Service(
        HaHealthServiceEnvelope(200, _ready_payload(), {"Cache-Control": "no-store"})
    )
    reader = _module().PepHealthReader(service_client=service, signer=signer)
    result = await reader.read(ha_user_id="synthetic-ha-subject", person=_context())

    assert signer.subjects == ["synthetic-ha-subject"]
    assert service.assertions == ["synthetic-assertion-1"]
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
    result = await _read(
        _unavailable_payload(), _context(pep_person_id="person_b", health_profile_id="kirsty")
    )

    assert result.status == "UNAVAILABLE"
    assert result.reason == "HEALTH_PROFILE_NOT_MAPPED"
    assert result.pep_person_id == "person_b"
    assert result.health_profile_id is None
    assert result.body == {}
    assert result.recovery == {}
    assert result.sleep == {}
    assert result.progress is None


def _numeric_paths() -> list[tuple[str, ...]]:
    return [
        (group, metric, "value")
        for group in ("body", "activity", "recovery", "sleep")
        for metric in _ready_payload()[group]
    ] + [
        ("readiness", "usable_observation_count"),
        ("progress", "fat_mass_change_28d_kg"),
        ("progress", "waist_change_28d_cm"),
        ("progress", "ffm_change_28d_kg"),
        ("progress", "total_weight_loss_28d_kg"),
        ("progress", "ffm_loss_ratio_pct"),
    ]


def _replace(payload: dict[str, Any], path: tuple[str, ...], value: object) -> None:
    target = payload
    for field in path[:-1]:
        target = target[field]
    target[path[-1]] = value


@pytest.mark.asyncio
@pytest.mark.parametrize("path", _numeric_paths())
@pytest.mark.parametrize("value", [True, False, "12.5", float("inf"), float("nan")])
async def test_every_json_number_rejects_coercion_and_nonfinite_values(
    path: tuple[str, ...], value: object
) -> None:
    payload = _ready_payload()
    _replace(payload, path, value)
    result = await _read(payload)
    assert result.status == "UNAVAILABLE"
    assert result.reason == "INVALID_CONTRACT"
    assert result.body == result.recovery == result.sleep == {}
    assert result.progress is None


@pytest.mark.asyncio
@pytest.mark.parametrize("path", _numeric_paths())
@pytest.mark.parametrize("value", [12, 12.5])
async def test_every_json_number_accepts_genuine_integer_and_float(
    path: tuple[str, ...], value: int | float
) -> None:
    payload = _ready_payload()
    _replace(payload, path, value)
    result = await _read(payload)
    assert result.status == "READY"
    if path[0] in ("body", "recovery", "sleep"):
        assert getattr(result, path[0])[path[1]].value == value
    elif path[0] == "progress":
        assert getattr(result.progress, path[1]) == value


@pytest.mark.asyncio
@pytest.mark.parametrize("path", [("exported_at",), ("body", "body_mass", "recorded_at")])
@pytest.mark.parametrize(
    "value",
    [
        "invalid",
        "2026-10-01",
        "2026-10-01T06:30:00",
        123,
        "2026-13-01T06:30:00Z",
        "2026-10-01T06:30:00+00:60",
    ],
)
async def test_invalid_or_nonaware_timestamps_discard_entire_projection(
    path: tuple[str, ...], value: object
) -> None:
    payload = _ready_payload()
    _replace(payload, path, value)
    result = await _read(payload)
    assert result.status == "UNAVAILABLE"
    assert result.reason == "INVALID_CONTRACT"
    assert result.body == result.recovery == result.sleep == {}
    assert result.progress is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "value", ["2026-10-01T06:30:00Z", "2026-10-01T06:30:00z", "2026-10-01T07:30:00.123+01:00"]
)
async def test_aware_timestamps_are_preserved_without_interpretation(value: str) -> None:
    payload = _ready_payload()
    payload["exported_at"] = value
    payload["body"]["body_mass"]["recorded_at"] = value
    result = await _read(payload)
    assert result.status == "READY"
    assert result.exported_at == value
    assert result.body["body_mass"].recorded_at == value
    assert result.latest_recorded_at == value


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("automatic_action",), 0),
        (("causation_asserted",), 0),
        (("readiness", "ready"), "true"),
        (("body", "body_mass", "derived"), 0),
        (("progress", "body_recomposition"), 1),
        (("body", "body_mass", "private_notes"), "private-sentinel"),
        (("progress", "private_notes"), "private-sentinel"),
    ],
)
async def test_boolean_type_confusion_and_nested_extras_fail_closed(
    path: tuple[str, ...], value: object
) -> None:
    payload = _ready_payload()
    _replace(payload, path, value)
    result = await _read(payload)
    assert result.status == "UNAVAILABLE"
    assert result.reason == "INVALID_CONTRACT"
    assert result.body == result.recovery == result.sleep == {}
    assert result.progress is None


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["success", "unavailable", "cross-person", "transport-failure"])
async def test_sequential_person_switch_never_reuses_subject_or_metrics(outcome: str) -> None:
    signer = _Signer()
    service = _Service(
        HaHealthServiceEnvelope(200, _ready_payload(), {"Cache-Control": "no-store"})
    )
    reader = _module().PepHealthReader(service_client=service, signer=signer)
    first = await reader.read(ha_user_id="synthetic-ha-a", person=_context())
    assert first.status == "READY"
    second_payload = _ready_payload(person_id="person_b", health_profile_id="kirsty")
    second_payload["body"]["body_mass"]["value"] = 60.0
    if outcome == "unavailable":
        second_payload["readiness"]["ready"] = False
        second_payload["readiness"]["reason"] = "DATASET_STALE"
    elif outcome == "cross-person":
        second_payload = _ready_payload()
    service.result = (
        HaHealthServiceFailure()
        if outcome == "transport-failure"
        else HaHealthServiceEnvelope(200, second_payload, {"Cache-Control": "no-store"})
    )
    second = await reader.read(
        ha_user_id="synthetic-ha-b",
        person=_context(pep_person_id="person_b", health_profile_id="kirsty"),
    )
    assert signer.subjects == ["synthetic-ha-a", "synthetic-ha-b"]
    assert service.assertions == ["synthetic-assertion-1", "synthetic-assertion-2"]
    assert second.pep_person_id == "person_b"
    if outcome == "success":
        assert second.status == "READY"
        assert second.health_profile_id == "kirsty"
        assert second.body["body_mass"].value == 60.0
    else:
        assert second.status == "UNAVAILABLE"
        assert second.body == second.recovery == second.sleep == {}
        assert second.progress is None
        assert second.latest_recorded_at is None
        assert second.runtime_version != first.runtime_version or outcome == "unavailable"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reason",
    [
        "HEALTH_AUTHORITY_DISABLED",
        "SERVICE_ASSERTION_STARTUP_QUARANTINE",
        "INVALID_SERVICE_ASSERTION",
        "PERSON_CONTEXT_UNAVAILABLE",
        "ASSERTION_RATE_LIMITED",
        "COMPUTE_FAILED",
        "private-sentinel",
    ],
)
async def test_governed_errors_are_allowlisted_and_never_retried(reason: str) -> None:
    signer = _Signer()
    status = {
        "INVALID_SERVICE_ASSERTION": 401,
        "PERSON_CONTEXT_UNAVAILABLE": 403,
        "ASSERTION_RATE_LIMITED": 429,
    }.get(reason, 503)
    service = _Service(
        HaHealthServiceEnvelope(status, {"error": reason}, {"Cache-Control": "no-store"})
    )
    reader = _module().PepHealthReader(service_client=service, signer=signer)
    result = await reader.read(ha_user_id="synthetic-ha-a", person=_context())
    expected = (
        reason if reason not in ("COMPUTE_FAILED", "private-sentinel") else "PEP_HEALTH_UNAVAILABLE"
    )
    assert result.status == "UNAVAILABLE"
    assert result.reason == expected
    assert result.body == result.recovery == result.sleep == {}
    assert result.progress is None
    assert service.assertions == ["synthetic-assertion-1"]


@pytest.mark.asyncio
async def test_cancellation_propagates_without_retry() -> None:
    class CancelledService(_Service):
        async def get_health_context(self, assertion: str) -> HaHealthServiceFailure:
            self.assertions.append(assertion)
            raise asyncio.CancelledError

    service = CancelledService(HaHealthServiceFailure())
    reader = _module().PepHealthReader(service_client=service, signer=_Signer())
    with pytest.raises(asyncio.CancelledError):
        await reader.read(ha_user_id="synthetic-ha-a", person=_context())
    assert service.assertions == ["synthetic-assertion-1"]


@pytest.mark.asyncio
@pytest.mark.parametrize("ha_user_id", ["", "  ", None, True])
async def test_missing_subject_cannot_fall_back_to_local_identity(ha_user_id: Any) -> None:
    signer = _Signer()
    service = _Service(
        HaHealthServiceEnvelope(200, _ready_payload(), {"Cache-Control": "no-store"})
    )
    reader = _module().PepHealthReader(service_client=service, signer=signer)
    result = await reader.read(ha_user_id=ha_user_id, person=_context())
    assert result.status == "UNAVAILABLE"
    assert result.reason == "PEP_HEALTH_UNAVAILABLE"
    assert result.body == {}
    assert signer.subjects == service.assertions == []


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_at", ["signer", "service"])
async def test_dependency_failure_is_private_unavailable_without_retry(
    failure_at: str, caplog: pytest.LogCaptureFixture
) -> None:
    class FailingSigner(_Signer):
        def sign(self, subject: str) -> str:
            assertion = super().sign(subject)
            if failure_at == "signer":
                raise ValueError("synthetic-private-sentinel")
            return assertion

    class FailingService(_Service):
        async def get_health_context(self, assertion: str) -> HaHealthServiceFailure:
            self.assertions.append(assertion)
            raise TimeoutError("synthetic-private-sentinel")

    signer = FailingSigner()
    service = FailingService(HaHealthServiceFailure())
    reader = _module().PepHealthReader(service_client=service, signer=signer)
    result = await reader.read(ha_user_id="synthetic-ha-sentinel", person=_context())
    assert result.status == "UNAVAILABLE"
    assert result.reason == "PEP_HEALTH_UNAVAILABLE"
    assert result.body == result.recovery == result.sleep == {}
    assert result.progress is None
    assert signer.subjects == ["synthetic-ha-sentinel"]
    assert service.assertions == ([] if failure_at == "signer" else ["synthetic-assertion-1"])
    assert "synthetic-private-sentinel" not in caplog.text
    assert "synthetic-ha-sentinel" not in caplog.text
    assert "synthetic-assertion" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        _ready_payload(),
        {"status_code": 200, "body": _ready_payload(), "headers": {"Cache-Control": "no-store"}},
        {"id": 1, "type": "result", "success": True, "result": {"response": _ready_payload()}},
        HaHealthServiceEnvelope(True, _ready_payload(), {"Cache-Control": "no-store"}),
        HaHealthServiceEnvelope(200, _ready_payload(), {}),
        HaHealthServiceEnvelope(200, [], {"Cache-Control": "no-store"}),
    ],
)
async def test_reader_accepts_only_valid_typed_service_result(response: Any) -> None:
    service = _Service(response)
    reader = _module().PepHealthReader(service_client=service, signer=_Signer())
    result = await reader.read(ha_user_id="synthetic-ha-subject", person=_context())
    assert result.status == "UNAVAILABLE"
    assert result.reason == "PEP_HEALTH_UNAVAILABLE"
    assert result.body == result.recovery == result.sleep == {}
    assert result.progress is None


@pytest.mark.asyncio
async def test_governed_error_code_on_wrong_http_status_is_unavailable() -> None:
    service = _Service(
        HaHealthServiceEnvelope(
            500, {"error": "INVALID_SERVICE_ASSERTION"}, {"Cache-Control": "no-store"}
        )
    )
    reader = _module().PepHealthReader(service_client=service, signer=_Signer())
    result = await reader.read(ha_user_id="synthetic-ha-subject", person=_context())
    assert result.status == "UNAVAILABLE"
    assert result.reason == "PEP_HEALTH_UNAVAILABLE"


@pytest.mark.asyncio
async def test_reader_rejects_cross_person_payload() -> None:
    result = await _read(_ready_payload(person_id="person_b", health_profile_id="kirsty"))

    assert result.status == "UNAVAILABLE"
    assert result.reason == "PERSON_CONTEXT_MISMATCH"


@pytest.mark.asyncio
async def test_reader_rejects_ready_health_profile_mismatch() -> None:
    result = await _read(_ready_payload(health_profile_id="other"))

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
    payload = _ready_payload()
    payload[field] = value
    result = await _read(payload)

    assert result.status == "UNAVAILABLE"
    assert result.reason == "CONTRACT_SCHEMA_MISMATCH"


@pytest.mark.asyncio
async def test_reader_rejects_sensitive_extra_fields() -> None:
    payload = _ready_payload()
    payload["dose"] = {"compound": "must-never-enter-getfit"}
    result = await _read(payload)

    assert result.status == "UNAVAILABLE"
    assert result.reason == "INVALID_CONTRACT"


@pytest.mark.asyncio
async def test_reader_preserves_pep_unavailable_state_without_smoothing() -> None:
    payload = _ready_payload()
    payload["readiness"] = {
        "ready": False,
        "state": "UNAVAILABLE",
        "reason": "DATASET_STALE",
        "usable_observation_count": 8,
        "data_quality": "UNAVAILABLE",
    }

    result = await _read(payload)

    assert result.status == "UNAVAILABLE"
    assert result.reason == "DATASET_STALE"
    assert result.source_state == "UNAVAILABLE"
    assert result.data_quality == "UNAVAILABLE"
    assert result.body == {}


@pytest.mark.asyncio
async def test_reader_degrades_on_transport_failure() -> None:
    reader = _module().PepHealthReader(
        service_client=_Service(HaHealthServiceFailure()), signer=_Signer()
    )
    result = await reader.read(ha_user_id="synthetic-ha-subject", person=_context())

    assert result.status == "UNAVAILABLE"
    assert result.reason == "PEP_HEALTH_UNAVAILABLE"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "reason"),
    [
        (("schema_version",), "CONTRACT_SCHEMA_MISMATCH"),
        (("body", "body_mass", "value"), "INVALID_CONTRACT"),
        (("readiness", "usable_observation_count"), "INVALID_CONTRACT"),
        (("progress", "total_weight_loss_28d_kg"), "INVALID_CONTRACT"),
    ],
    ids=["boolean-version", "boolean-metric", "boolean-count", "boolean-progress"],
)
async def test_reader_rejects_boolean_numeric_contract_fields(
    path: tuple[str, ...], reason: str
) -> None:
    # Removing strict scalar checks must expose no partial Health context.
    payload = _ready_payload()
    target = payload
    for field in path[:-1]:
        target = target[field]
    target[path[-1]] = True

    result = await _read(payload)
    assert result.status == "UNAVAILABLE"
    assert result.reason == reason
    assert result.body == {}
    assert result.recovery == {}
    assert result.sleep == {}
    assert result.progress is None
