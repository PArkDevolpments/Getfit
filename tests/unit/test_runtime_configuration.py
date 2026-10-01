from decimal import Decimal

import hwa.runtime as runtime
from hwa.domain.equipment import EquipmentKind


def test_runtime_equipment_profile_uses_explicit_installation_configuration(monkeypatch) -> None:
    monkeypatch.setenv("HWA_TREADMILL_AVAILABLE", "true")
    monkeypatch.setenv("HWA_TREADMILL_MAX_INCLINE_PERCENT", "20")
    monkeypatch.setenv("HWA_SPIN_BIKE_AVAILABLE", "true")
    monkeypatch.setenv("HWA_ADJUSTABLE_DUMBBELLS_AVAILABLE", "true")

    profile = runtime.build_installation_equipment_profile()
    by_kind = {item.kind: item for item in profile.equipment}

    treadmill = by_kind[EquipmentKind.TREADMILL]
    assert treadmill.available is True
    assert treadmill.supports_speed is True
    assert treadmill.supports_incline is True
    assert treadmill.max_incline_percent == Decimal("20")

    bike = by_kind[EquipmentKind.SPIN_BIKE]
    assert bike.available is True
    assert bike.supports_incline is False
    assert bike.max_incline_percent is None
    assert bike.supports_cadence is True
    assert bike.supports_resistance is True

    dumbbells = by_kind[EquipmentKind.ADJUSTABLE_DUMBBELLS]
    assert dumbbells.available is True


def test_runtime_rejects_invalid_boolean_configuration(monkeypatch) -> None:
    monkeypatch.setenv("HWA_TREADMILL_AVAILABLE", "maybe")

    try:
        runtime.build_installation_equipment_profile()
    except ValueError as exc:
        assert "HWA_TREADMILL_AVAILABLE" in str(exc)
    else:
        raise AssertionError("invalid boolean configuration must fail closed")


def test_runtime_bootstrap_config_normalizes_optional_home_assistant_ids(monkeypatch) -> None:
    monkeypatch.setenv("HWA_KRIS_HA_USER_ID", "  ha-user-kris  ")
    monkeypatch.setenv("HWA_KIRSTY_HA_USER_ID", "   ")

    config = runtime.build_production_bootstrap_config()

    assert config.kris_ha_user_id == "ha-user-kris"
    assert config.kirsty_ha_user_id is None


def test_runtime_bootstrap_config_allows_both_home_assistant_ids_to_be_unconfigured(
    monkeypatch,
) -> None:
    monkeypatch.delenv("HWA_KRIS_HA_USER_ID", raising=False)
    monkeypatch.delenv("HWA_KIRSTY_HA_USER_ID", raising=False)

    config = runtime.build_production_bootstrap_config()

    assert config.kris_ha_user_id is None
    assert config.kirsty_ha_user_id is None
