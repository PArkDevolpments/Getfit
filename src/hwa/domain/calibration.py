"""Person-scoped calibration decisions without demographic load formulas."""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class CalibrationStatus(StrEnum):
    READY = "READY"
    CALIBRATED = "CALIBRATED"
    REQUIRED = "REQUIRED"


@dataclass(frozen=True, slots=True)
class CalibrationDecision:
    person_id: str
    exercise_id: str
    status: CalibrationStatus
    effective_load: Decimal | None
    load_unit: str | None
    source: str | None
    reason: str


def assess_strength_calibration(
    *,
    person_id: str,
    exercise_id: str,
    approved_load: Decimal | None,
    approved_load_unit: str | None,
    user_confirmed_load: Decimal | None,
    user_confirmed_load_unit: str | None,
) -> CalibrationDecision:
    """Resolve a strength starting target from approved or explicitly confirmed data.

    The API intentionally has no sex/bodyweight inputs. If neither an approved
    target nor an explicit user calibration exists, the target remains unknown.
    """

    if user_confirmed_load is not None:
        if user_confirmed_load <= 0 or not user_confirmed_load_unit:
            return CalibrationDecision(
                person_id=person_id,
                exercise_id=exercise_id,
                status=CalibrationStatus.REQUIRED,
                effective_load=None,
                load_unit=None,
                source=None,
                reason="A valid explicit calibration load and unit are required.",
            )
        return CalibrationDecision(
            person_id=person_id,
            exercise_id=exercise_id,
            status=CalibrationStatus.CALIBRATED,
            effective_load=user_confirmed_load,
            load_unit=user_confirmed_load_unit,
            source="USER_CONFIRMED",
            reason="Using the load explicitly confirmed during individual calibration.",
        )

    if approved_load is not None and approved_load > 0 and approved_load_unit:
        return CalibrationDecision(
            person_id=person_id,
            exercise_id=exercise_id,
            status=CalibrationStatus.READY,
            effective_load=approved_load,
            load_unit=approved_load_unit,
            source="APPROVED_PROGRAMME",
            reason="Retaining the existing approved programme target.",
        )

    return CalibrationDecision(
        person_id=person_id,
        exercise_id=exercise_id,
        status=CalibrationStatus.REQUIRED,
        effective_load=None,
        load_unit=None,
        source=None,
        reason="No approved or user-confirmed target exists; individual calibration is required.",
    )
