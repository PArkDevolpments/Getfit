from decimal import Decimal
from inspect import signature

from hwa.domain.calibration import CalibrationStatus, assess_strength_calibration


def test_missing_target_requests_calibration_instead_of_deriving_from_profile() -> None:
    decision = assess_strength_calibration(
        person_id="hwa-kris",
        exercise_id="goblet-squat",
        approved_load=None,
        approved_load_unit=None,
        user_confirmed_load=None,
        user_confirmed_load_unit=None,
    )

    assert decision.status is CalibrationStatus.REQUIRED
    assert decision.effective_load is None
    assert "calibration" in decision.reason.lower()


def test_explicit_user_confirmed_calibration_is_person_scoped_and_explainable() -> None:
    decision = assess_strength_calibration(
        person_id="hwa-kris",
        exercise_id="goblet-squat",
        approved_load=None,
        approved_load_unit=None,
        user_confirmed_load=Decimal("10.0"),
        user_confirmed_load_unit="KG",
    )

    assert decision.status is CalibrationStatus.CALIBRATED
    assert decision.person_id == "hwa-kris"
    assert decision.effective_load == Decimal("10.0")
    assert decision.source == "USER_CONFIRMED"


def test_existing_approved_target_is_retained_without_profile_math() -> None:
    decision = assess_strength_calibration(
        person_id="hwa-kirsty",
        exercise_id="floor-press",
        approved_load=Decimal("8.0"),
        approved_load_unit="KG",
        user_confirmed_load=None,
        user_confirmed_load_unit=None,
    )

    assert decision.status is CalibrationStatus.READY
    assert decision.effective_load == Decimal("8.0")
    assert decision.source == "APPROVED_PROGRAMME"


def test_calibration_api_has_no_sex_or_bodyweight_load_inputs() -> None:
    parameters = signature(assess_strength_calibration).parameters
    assert "sex" not in parameters
    assert "bodyweight" not in parameters
    assert "weight_kg" not in parameters
