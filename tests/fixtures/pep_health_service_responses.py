"""Synthetic Pep v1 and complete HA service/WebSocket response builders."""

from typing import Any


def metric(name: str, value: float | None, unit: str) -> dict[str, Any]:
    return {
        "status": "available" if value is not None else "unavailable",
        "metric": name,
        "value": value,
        "unit": unit,
        "recorded_at": "2026-10-01T06:30:00Z" if value is not None else None,
        "derived": False,
        "reason": "OK" if value is not None else "METRIC_UNAVAILABLE",
    }


def ready_projection(
    *, person_id: str = "synthetic-person-a", health_profile_id: str = "synthetic-profile-a"
) -> dict[str, Any]:
    groups = {
        "body": {
            "body_mass": (80.0, "kg"),
            "height": (1.8, "m"),
            "body_fat_percentage": (20.0, "%"),
            "lean_body_mass": (64.0, "kg"),
            "fat_mass": (16.0, "kg"),
            "waist_circumference": (None, "cm"),
            "muscle_mass": (None, "kg"),
            "bmi": (None, "kg/m²"),
        },
        "activity": {
            "steps": (6000.0, "steps"),
            "exercise_time": (30.0, "min"),
            "active_calories": (400.0, "kcal"),
            "distance": (4000.0, "m"),
        },
        "recovery": {
            "resting_heart_rate": (60.0, "bpm"),
            "heart_rate_variability": (45.0, "ms"),
            "vo2_max": (35.0, "mL/kg/min"),
            "cardio_recovery": (25.0, "bpm"),
            "oxygen_saturation": (98.0, "%"),
            "respiratory_rate": (14.0, "breaths/min"),
        },
        "sleep": {
            "sleep_duration": (7.0, "h"),
            "sleep_core_hours": (4.0, "h"),
            "sleep_rem_hours": (1.5, "h"),
            "sleep_deep_hours": (1.0, "h"),
            "sleep_awake_hours": (0.5, "h"),
        },
    }
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
            "flags": [],
        },
        **{
            group: {name: metric(name, value, unit) for name, (value, unit) in fields.items()}
            for group, fields in groups.items()
        },
        "progress": {
            "semantics": "28_DAY_TREND_DERIVED",
            "fat_mass_change_28d_kg": -1.0,
            "waist_change_28d_cm": None,
            "ffm_change_28d_kg": 0.0,
            "total_weight_loss_28d_kg": 1.0,
            "ffm_loss_ratio_pct": 0.0,
            "body_recomposition": False,
            "confidence": "HIGH",
            "data_quality": "GOOD",
        },
        "domains": [
            {
                "domain_id": "weight",
                "state": "AVAILABLE",
                "reason": "OK",
                "ready": True,
                "decision_eligible": True,
            }
        ],
        "provenance": {"authority": "PEPTIDE_SITE_HEALTH", "runtime_version": "synthetic-v1"},
        "automatic_action": False,
        "causation_asserted": False,
    }


def service_response(
    body: dict[str, Any] | None = None, *, status_code: int = 200
) -> dict[str, Any]:
    return {
        "status_code": status_code,
        "body": ready_projection() if body is None else body,
        "headers": {"Cache-Control": "no-store"},
    }


def websocket_result(response: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": 1,
        "type": "result",
        "success": True,
        "result": {"response": service_response() if response is None else response},
    }


def governed_error(reason: str, *, status_code: int = 503) -> dict[str, Any]:
    return websocket_result(service_response({"error": reason}, status_code=status_code))
