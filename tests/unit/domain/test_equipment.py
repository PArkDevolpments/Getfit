from decimal import Decimal

import pytest
from pydantic import ValidationError

from hwa.domain.equipment import (
    EquipmentCapability,
    EquipmentKind,
    InstallationEquipmentProfile,
)


def test_treadmill_can_declare_speed_and_twenty_percent_incline_capability() -> None:
    treadmill = EquipmentCapability(
        kind=EquipmentKind.TREADMILL,
        label="Treadmill",
        available=True,
        supports_speed=True,
        supports_incline=True,
        max_incline_percent=Decimal("20"),
        supports_cadence=False,
        supports_resistance=False,
    )

    assert treadmill.supports_speed is True
    assert treadmill.supports_incline is True
    assert treadmill.max_incline_percent == Decimal("20")


def test_spin_bike_structurally_rejects_incline_capability() -> None:
    with pytest.raises(ValidationError, match="spin bike cannot support incline"):
        EquipmentCapability(
            kind=EquipmentKind.SPIN_BIKE,
            label="Spin bike",
            available=True,
            supports_speed=False,
            supports_incline=True,
            max_incline_percent=Decimal("1"),
            supports_cadence=True,
            supports_resistance=True,
        )


def test_spin_bike_supports_cadence_and_resistance_without_speed_or_incline() -> None:
    bike = EquipmentCapability(
        kind=EquipmentKind.SPIN_BIKE,
        label="Spin bike",
        available=True,
        supports_speed=False,
        supports_incline=False,
        supports_cadence=True,
        supports_resistance=True,
    )

    assert bike.supports_cadence is True
    assert bike.supports_resistance is True
    assert bike.supports_speed is False
    assert bike.supports_incline is False
    assert bike.max_incline_percent is None


def test_adjustable_dumbbells_do_not_gain_cardio_capabilities() -> None:
    dumbbells = EquipmentCapability(
        kind=EquipmentKind.ADJUSTABLE_DUMBBELLS,
        label="Adjustable dumbbells",
        available=True,
    )

    assert dumbbells.supports_speed is False
    assert dumbbells.supports_incline is False
    assert dumbbells.supports_cadence is False
    assert dumbbells.supports_resistance is False


def test_incline_limit_requires_incline_support_and_cannot_be_negative() -> None:
    with pytest.raises(ValidationError):
        EquipmentCapability(
            kind=EquipmentKind.TREADMILL,
            label="Treadmill",
            available=True,
            supports_speed=True,
            supports_incline=False,
            max_incline_percent=Decimal("20"),
        )

    with pytest.raises(ValidationError):
        EquipmentCapability(
            kind=EquipmentKind.TREADMILL,
            label="Treadmill",
            available=True,
            supports_speed=True,
            supports_incline=True,
            max_incline_percent=Decimal("-1"),
        )


def test_installation_profile_rejects_duplicate_equipment_kinds() -> None:
    treadmill = EquipmentCapability(
        kind=EquipmentKind.TREADMILL,
        label="Treadmill",
        available=True,
        supports_speed=True,
        supports_incline=True,
        max_incline_percent=Decimal("20"),
    )

    with pytest.raises(ValidationError, match="duplicate equipment kind"):
        InstallationEquipmentProfile(equipment=(treadmill, treadmill))
