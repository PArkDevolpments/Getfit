"""Presentation-only context projected from external Health and Nutrition authorities."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from hwa.integrations.menu.reader import MenuNutritionContext
    from hwa.integrations.pep.health_reader import PepHealthContext, PepHealthMetric


class StrictContextModel(BaseModel):
    """Immutable closed model for presentation context."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ContextMetric(StrictContextModel):
    value: float
    unit: str
    recorded_at: str | None = None


class NutritionTarget(StrictContextModel):
    calories_kcal: float
    protein_g: float
    carbohydrate_g: float
    fat_g: float


class NutritionDay(StrictContextModel):
    date: str
    recorded_at: str
    logging_status: str
    energy_consumed_kcal: float | None = None
    protein_g: float | None = None
    carbohydrate_g: float | None = None
    fat_g: float | None = None


class HealthExternalContext(StrictContextModel):
    status: Literal["READY", "UNAVAILABLE"]
    reason: str
    data_quality: str | None = None
    latest_recorded_at: str | None = None
    body_mass: ContextMetric | None = None
    sleep_duration: ContextMetric | None = None


class NutritionExternalContext(StrictContextModel):
    status: Literal["READY", "UNAVAILABLE"]
    reason: str
    generated_at: str | None = None
    current_target: NutritionTarget | None = None
    latest_day: NutritionDay | None = None


class ExternalContext(StrictContextModel):
    """External context that can inform presentation but never own workout decisions."""

    health: HealthExternalContext
    nutrition: NutritionExternalContext
    presentation_only: Literal[True] = True
    automatic_action: Literal[False] = False


def _available_metric(metric: PepHealthMetric | None) -> ContextMetric | None:
    if metric is None or metric.status != "available" or metric.value is None:
        return None
    return ContextMetric(
        value=metric.value,
        unit=metric.unit,
        recorded_at=metric.recorded_at,
    )


def _health_context(source: PepHealthContext) -> HealthExternalContext:
    if source.status != "READY":
        return HealthExternalContext(status="UNAVAILABLE", reason=source.reason)
    return HealthExternalContext(
        status="READY",
        reason=source.reason,
        data_quality=source.data_quality,
        latest_recorded_at=source.latest_recorded_at,
        body_mass=_available_metric(source.body.get("body_mass")),
        sleep_duration=_available_metric(source.sleep.get("sleep_duration")),
    )


def _nutrition_context(source: MenuNutritionContext) -> NutritionExternalContext:
    if source.status != "READY":
        return NutritionExternalContext(status="UNAVAILABLE", reason=source.reason)

    target = None
    if source.current_target is not None:
        target = NutritionTarget(
            calories_kcal=source.current_target.calories_kcal,
            protein_g=source.current_target.protein_g,
            carbohydrate_g=source.current_target.carbohydrate_g,
            fat_g=source.current_target.fat_g,
        )

    latest = None
    if source.days:
        row = max(source.days, key=lambda item: (item.date, item.recorded_at))
        latest = NutritionDay(
            date=row.date,
            recorded_at=row.recorded_at,
            logging_status=row.logging_status,
            energy_consumed_kcal=row.energy_consumed_kcal,
            protein_g=row.protein_g,
            carbohydrate_g=row.carbohydrate_g,
            fat_g=row.fat_g,
        )

    return NutritionExternalContext(
        status="READY",
        reason=source.reason,
        generated_at=source.generated_at,
        current_target=target,
        latest_day=latest,
    )


def build_external_context(
    pep: PepHealthContext,
    menu: MenuNutritionContext,
) -> ExternalContext:
    """Project only approved presentation values without cross-authority fallback."""

    return ExternalContext(
        health=_health_context(pep),
        nutrition=_nutrition_context(menu),
    )
