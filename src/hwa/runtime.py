"""Production runtime wiring for the Home Assistant app."""

from __future__ import annotations

import os
from decimal import Decimal, InvalidOperation

from hwa.domain.equipment import (
    EquipmentCapability,
    EquipmentKind,
    InstallationEquipmentProfile,
)
from hwa.main import create_app


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default

    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value")


def _decimal_env(name: str, default: Decimal) -> Decimal:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = Decimal(raw.strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{name} must be a decimal value") from exc
    if value < 0:
        raise ValueError(f"{name} must not be negative")
    return value


def build_installation_equipment_profile() -> InstallationEquipmentProfile:
    """Build explicit installation capabilities from validated runtime configuration."""

    treadmill_max_incline = _decimal_env(
        "HWA_TREADMILL_MAX_INCLINE_PERCENT",
        Decimal("20"),
    )
    return InstallationEquipmentProfile(
        equipment=(
            EquipmentCapability(
                kind=EquipmentKind.TREADMILL,
                label="Treadmill",
                available=_bool_env("HWA_TREADMILL_AVAILABLE", True),
                supports_speed=True,
                supports_incline=True,
                max_incline_percent=treadmill_max_incline,
            ),
            EquipmentCapability(
                kind=EquipmentKind.SPIN_BIKE,
                label="Spin bike",
                available=_bool_env("HWA_SPIN_BIKE_AVAILABLE", True),
                supports_cadence=True,
                supports_resistance=True,
            ),
            EquipmentCapability(
                kind=EquipmentKind.ADJUSTABLE_DUMBBELLS,
                label="Adjustable dumbbells",
                available=_bool_env("HWA_ADJUSTABLE_DUMBBELLS_AVAILABLE", True),
            ),
        )
    )


app = create_app(equipment_profile=build_installation_equipment_profile())
