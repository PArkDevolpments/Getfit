from hwa.domain.external_context import build_external_context

from hwa.integrations.menu.reader import (
    MacroTargets,
    MenuNutritionContext,
    MenuNutritionDay,
)
from hwa.integrations.pep.health_reader import (
    PepHealthContext,
    PepHealthMetric,
)


def _metric(metric: str, value: float, unit: str) -> PepHealthMetric:
    return PepHealthMetric(
        status="available",
        metric=metric,
        value=value,
        unit=unit,
        recorded_at="2026-10-01T06:30:00Z",
        derived=False,
        reason="OK",
    )


def test_external_context_is_presentation_only_and_projects_approved_values() -> None:
    pep = PepHealthContext(
        status="READY",
        reason="OK",
        pep_person_id="person_a",
        health_profile_id="kris",
        data_quality="GOOD",
        latest_recorded_at="2026-10-01T06:30:00Z",
        body={"body_mass": _metric("body_mass", 113.7, "kg")},
        sleep={"sleep_duration": _metric("sleep_duration", 7.2, "h")},
    )
    menu = MenuNutritionContext(
        status="READY",
        reason="OK",
        menu_person_id="person_1",
        generated_at="2026-10-01T07:00:00Z",
        current_target=MacroTargets(
            calories_kcal=2150,
            protein_g=180,
            carbohydrate_g=190,
            fat_g=70,
        ),
        days=(
            MenuNutritionDay(
                date="2026-10-01",
                recorded_at="2026-10-01T21:00:00Z",
                atomic_evidence_id="menu-person_1-2026-10-01",
                decision_eligible=True,
                logging_complete=True,
                logging_status="complete",
                energy_consumed_kcal=2050,
                protein_g=176,
                carbohydrate_g=182,
                fat_g=68,
                dietary_adherence={},
            ),
        ),
    )

    context = build_external_context(pep, menu)

    assert context.presentation_only is True
    assert context.automatic_action is False
    assert context.health.status == "READY"
    assert context.health.body_mass is not None
    assert context.health.body_mass.value == 113.7
    assert context.health.sleep_duration is not None
    assert context.health.sleep_duration.value == 7.2
    assert context.nutrition.status == "READY"
    assert context.nutrition.current_target is not None
    assert context.nutrition.current_target.calories_kcal == 2150
    assert context.nutrition.latest_day is not None
    assert context.nutrition.latest_day.energy_consumed_kcal == 2050


def test_unavailable_authority_never_falls_back_to_the_other_source() -> None:
    pep = PepHealthContext(
        status="UNAVAILABLE",
        reason="DATASET_STALE",
        pep_person_id="person_a",
    )
    menu = MenuNutritionContext(
        status="READY",
        reason="OK",
        menu_person_id="person_1",
        current_target=MacroTargets(
            calories_kcal=2150,
            protein_g=180,
            carbohydrate_g=190,
            fat_g=70,
        ),
    )

    context = build_external_context(pep, menu)

    assert context.health.status == "UNAVAILABLE"
    assert context.health.reason == "DATASET_STALE"
    assert context.health.body_mass is None
    assert context.health.sleep_duration is None
    assert context.nutrition.status == "READY"
