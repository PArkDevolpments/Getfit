"""Safe presentation model for equipment, calibration and integration state."""

from dataclasses import dataclass
from decimal import Decimal

from hwa.domain.equipment import EquipmentKind, InstallationEquipmentProfile
from hwa.domain.identity import PersonContext


@dataclass(frozen=True, slots=True)
class EquipmentSettingsRow:
    label: str
    available: bool
    capability_notes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IntegrationSettingsRow:
    label: str
    status: str


@dataclass(frozen=True, slots=True)
class CalibrationSettings:
    label: str
    status: str
    detail: str


@dataclass(frozen=True, slots=True)
class SettingsView:
    equipment_configured: bool
    equipment: tuple[EquipmentSettingsRow, ...]
    calibration: CalibrationSettings
    integrations: tuple[IntegrationSettingsRow, ...]


def _format_decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _equipment_rows(
    profile: InstallationEquipmentProfile | None,
) -> tuple[EquipmentSettingsRow, ...]:
    if profile is None:
        return ()

    rows: list[EquipmentSettingsRow] = []
    for item in profile.equipment:
        notes: list[str] = []
        if item.kind is EquipmentKind.TREADMILL:
            if item.supports_speed:
                notes.append("Speed supported")
            if item.supports_incline and item.max_incline_percent is not None:
                notes.append(f"Incline up to {_format_decimal(item.max_incline_percent)}%")
            else:
                notes.append("No incline")
        elif item.kind is EquipmentKind.SPIN_BIKE:
            notes.append("No incline")
            if item.supports_cadence:
                notes.append("Cadence supported")
            if item.supports_resistance:
                notes.append("Resistance supported")
        elif item.kind is EquipmentKind.ADJUSTABLE_DUMBBELLS:
            notes.append("External load available")

        rows.append(
            EquipmentSettingsRow(
                label=item.label,
                available=item.available,
                capability_notes=tuple(notes),
            )
        )
    return tuple(rows)


def build_settings_view(
    person: PersonContext,
    equipment_profile: InstallationEquipmentProfile | None,
    *,
    pep_health_configured: bool,
    menu_nutrition_configured: bool,
) -> SettingsView:
    """Build a person-safe view without exposing authority identifiers or secrets."""

    del person
    return SettingsView(
        equipment_configured=equipment_profile is not None,
        equipment=_equipment_rows(equipment_profile),
        calibration=CalibrationSettings(
            label="Individual calibration",
            status="As needed",
            detail=(
                "Starting targets and progression use approved targets and performed evidence; "
                "they are never inferred from demographic profile fields."
            ),
        ),
        integrations=(
            IntegrationSettingsRow(
                label="Pep Health",
                status="Configured" if pep_health_configured else "Not configured",
            ),
            IntegrationSettingsRow(
                label="Menu-Nutrition",
                status="Configured" if menu_nutrition_configured else "Not configured",
            ),
        ),
    )
