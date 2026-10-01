"""Installation-level equipment capability contracts."""

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EquipmentKind(StrEnum):
    TREADMILL = "TREADMILL"
    SPIN_BIKE = "SPIN_BIKE"
    ADJUSTABLE_DUMBBELLS = "ADJUSTABLE_DUMBBELLS"


class StrictEquipmentModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EquipmentCapability(StrictEquipmentModel):
    """One installation-level equipment capability record."""

    kind: EquipmentKind
    label: str = Field(min_length=1)
    available: bool
    supports_speed: bool = False
    supports_incline: bool = False
    max_incline_percent: Decimal | None = Field(default=None, ge=0)
    supports_cadence: bool = False
    supports_resistance: bool = False

    @model_validator(mode="after")
    def validate_capability_semantics(self) -> "EquipmentCapability":
        if self.supports_incline and self.max_incline_percent is None:
            raise ValueError("incline support requires an explicit maximum incline")
        if not self.supports_incline and self.max_incline_percent is not None:
            raise ValueError("incline limit requires incline support")

        if self.kind is EquipmentKind.SPIN_BIKE:
            if self.supports_incline or self.max_incline_percent is not None:
                raise ValueError("spin bike cannot support incline")
            if self.supports_speed:
                raise ValueError("spin bike cannot expose treadmill speed capability")

        if self.kind is EquipmentKind.TREADMILL:
            if not self.supports_speed:
                raise ValueError("treadmill must expose speed capability")
            if self.supports_cadence or self.supports_resistance:
                raise ValueError("treadmill cannot expose bike cadence/resistance capabilities")

        if self.kind is EquipmentKind.ADJUSTABLE_DUMBBELLS and any(
            (
                self.supports_speed,
                self.supports_incline,
                self.supports_cadence,
                self.supports_resistance,
                self.max_incline_percent is not None,
            )
        ):
            raise ValueError("adjustable dumbbells cannot expose cardio capabilities")

        return self


class InstallationEquipmentProfile(StrictEquipmentModel):
    """Installation-level equipment inventory, separate from person identity."""

    equipment: tuple[EquipmentCapability, ...]

    @model_validator(mode="after")
    def unique_equipment_kinds(self) -> "InstallationEquipmentProfile":
        kinds = [item.kind for item in self.equipment]
        if len(kinds) != len(set(kinds)):
            raise ValueError("duplicate equipment kind")
        return self
