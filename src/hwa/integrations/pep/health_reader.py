"""Typed, fail-closed reader for Pep-Site Health Context v1."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from hwa.domain.identity import PersonContext

PEP_HEALTH_SCHEMA = "peptide-site.health-context"
PEP_HEALTH_VERSION = 1
PEP_HEALTH_AUTHORITY = "PEPTIDE_SITE_HEALTH"
DEFAULT_HEALTH_CONTEXT_URL = "http://homeassistant.local/api/peptide_site/health-context"


class StrictModel(BaseModel):
    """Closed contract model matching Pep's additionalProperties=false policy."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class PepHealthMetric(StrictModel):
    status: Literal["available", "unavailable"]
    metric: str = Field(min_length=1)
    value: float | None
    unit: str
    recorded_at: str | None
    derived: bool
    reason: str = Field(min_length=1)
    basis: tuple[str, ...] | None = None


class PepHealthReadiness(StrictModel):
    ready: bool
    state: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    usable_observation_count: float = Field(ge=0)
    data_quality: str = Field(min_length=1)


class PepHealthJourney(StrictModel):
    status: Literal[
        "STRONG_PROGRESS",
        "PROGRESS",
        "STABLE_ON_TRACK",
        "MIXED_RESPONSE",
        "WATCH",
        "REVIEW",
        "CONCERNING",
        "UNKNOWN",
    ]
    verdict: str = Field(min_length=1)
    confidence: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    flags: tuple[str, ...]


class PepHealthBody(StrictModel):
    body_mass: PepHealthMetric
    height: PepHealthMetric
    body_fat_percentage: PepHealthMetric
    lean_body_mass: PepHealthMetric
    fat_mass: PepHealthMetric
    waist_circumference: PepHealthMetric
    muscle_mass: PepHealthMetric
    bmi: PepHealthMetric


class PepHealthActivity(StrictModel):
    steps: PepHealthMetric
    exercise_time: PepHealthMetric
    active_calories: PepHealthMetric
    distance: PepHealthMetric


class PepHealthRecovery(StrictModel):
    resting_heart_rate: PepHealthMetric
    heart_rate_variability: PepHealthMetric
    vo2_max: PepHealthMetric
    cardio_recovery: PepHealthMetric
    oxygen_saturation: PepHealthMetric
    respiratory_rate: PepHealthMetric


class PepHealthSleep(StrictModel):
    sleep_duration: PepHealthMetric
    sleep_core_hours: PepHealthMetric
    sleep_rem_hours: PepHealthMetric
    sleep_deep_hours: PepHealthMetric
    sleep_awake_hours: PepHealthMetric


class PepHealthProgress(StrictModel):
    semantics: Literal["28_DAY_TREND_DERIVED"]
    fat_mass_change_28d_kg: float | None
    waist_change_28d_cm: float | None
    ffm_change_28d_kg: float | None
    total_weight_loss_28d_kg: float | None
    ffm_loss_ratio_pct: float | None
    body_recomposition: bool | None
    confidence: str | None
    data_quality: str | None


class PepHealthDomain(StrictModel):
    domain_id: str = Field(min_length=1)
    state: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    ready: bool
    decision_eligible: bool


class PepHealthProvenance(StrictModel):
    authority: Literal["PEPTIDE_SITE_HEALTH"]
    runtime_version: str | None


class PepHealthContractV1(StrictModel):
    schema_name: Literal["peptide-site.health-context"] = Field(alias="schema")
    schema_version: Literal[1]
    authority: Literal["PEPTIDE_SITE_HEALTH"]
    exported_at: str
    person_id: str | None
    health_profile_id: str | None
    readiness: PepHealthReadiness
    journey: PepHealthJourney
    body: PepHealthBody
    activity: PepHealthActivity
    recovery: PepHealthRecovery
    sleep: PepHealthSleep
    progress: PepHealthProgress
    domains: tuple[PepHealthDomain, ...]
    provenance: PepHealthProvenance
    automatic_action: Literal[False]
    causation_asserted: Literal[False]


class PepHealthContext(BaseModel):
    """Minimal Pep-owned Health context exposed to the workout experience."""

    model_config = ConfigDict(frozen=True)

    status: Literal["READY", "UNAVAILABLE"]
    reason: str
    pep_person_id: str
    health_profile_id: str | None = None
    exported_at: str | None = None
    source_state: str | None = None
    data_quality: str | None = None
    latest_recorded_at: str | None = None
    runtime_version: str | None = None
    body: dict[str, PepHealthMetric] = Field(default_factory=dict)
    recovery: dict[str, PepHealthMetric] = Field(default_factory=dict)
    sleep: dict[str, PepHealthMetric] = Field(default_factory=dict)
    progress: PepHealthProgress | None = None


_BODY_FIELDS = (
    "body_mass",
    "height",
    "body_fat_percentage",
    "lean_body_mass",
    "fat_mass",
    "waist_circumference",
    "muscle_mass",
    "bmi",
)
_RECOVERY_FIELDS = (
    "resting_heart_rate",
    "heart_rate_variability",
    "vo2_max",
    "cardio_recovery",
    "oxygen_saturation",
    "respiratory_rate",
)
_SLEEP_FIELDS = (
    "sleep_duration",
    "sleep_core_hours",
    "sleep_rem_hours",
    "sleep_deep_hours",
    "sleep_awake_hours",
)


def _metric_map(group: BaseModel, names: tuple[str, ...]) -> dict[str, PepHealthMetric]:
    return {name: getattr(group, name) for name in names}


def _latest_recorded_at(groups: tuple[dict[str, PepHealthMetric], ...]) -> str | None:
    candidates: list[tuple[datetime, str]] = []
    for group in groups:
        for metric in group.values():
            if not metric.recorded_at:
                continue
            try:
                instant = datetime.fromisoformat(metric.recorded_at.replace("Z", "+00:00"))
            except ValueError:
                continue
            if instant.tzinfo is None:
                continue
            candidates.append((instant, metric.recorded_at))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


class PepHealthReader:
    """Read Pep's Health projection without acquiring Health authority."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        endpoint_url: str = DEFAULT_HEALTH_CONTEXT_URL,
    ) -> None:
        self._client = client
        self._endpoint_url = endpoint_url

    async def read(self, person: PersonContext) -> PepHealthContext:
        try:
            response = await self._client.get(self._endpoint_url)
            response.raise_for_status()
            payload: Any = response.json()
        except (httpx.HTTPError, ValueError, TypeError):
            return self._unavailable(person, "PEP_HEALTH_UNAVAILABLE")

        if not isinstance(payload, dict):
            return self._unavailable(person, "INVALID_CONTRACT")
        if (
            payload.get("schema") != PEP_HEALTH_SCHEMA
            or payload.get("schema_version") != PEP_HEALTH_VERSION
            or payload.get("authority") != PEP_HEALTH_AUTHORITY
        ):
            return self._unavailable(person, "CONTRACT_SCHEMA_MISMATCH")

        try:
            contract = PepHealthContractV1.model_validate(payload)
        except ValidationError:
            return self._unavailable(person, "INVALID_CONTRACT")

        if contract.person_id != person.pep_person_id:
            return self._unavailable(person, "PERSON_CONTEXT_MISMATCH")
        if (
            contract.health_profile_id is not None
            and contract.health_profile_id != person.health_profile_id
        ):
            return self._unavailable(person, "HEALTH_PROFILE_MISMATCH")

        if not contract.readiness.ready:
            return PepHealthContext(
                status="UNAVAILABLE",
                reason=contract.readiness.reason,
                pep_person_id=person.pep_person_id,
                health_profile_id=contract.health_profile_id,
                exported_at=contract.exported_at,
                source_state=contract.readiness.state,
                data_quality=contract.readiness.data_quality,
                runtime_version=contract.provenance.runtime_version,
            )
        if contract.health_profile_id != person.health_profile_id:
            return self._unavailable(person, "HEALTH_PROFILE_MISMATCH")

        body = _metric_map(contract.body, _BODY_FIELDS)
        recovery = _metric_map(contract.recovery, _RECOVERY_FIELDS)
        sleep = _metric_map(contract.sleep, _SLEEP_FIELDS)
        return PepHealthContext(
            status="READY",
            reason=contract.readiness.reason,
            pep_person_id=person.pep_person_id,
            health_profile_id=contract.health_profile_id,
            exported_at=contract.exported_at,
            source_state=contract.readiness.state,
            data_quality=contract.readiness.data_quality,
            latest_recorded_at=_latest_recorded_at((body, recovery, sleep)),
            runtime_version=contract.provenance.runtime_version,
            body=body,
            recovery=recovery,
            sleep=sleep,
            progress=contract.progress,
        )

    @staticmethod
    def _unavailable(person: PersonContext, reason: str) -> PepHealthContext:
        return PepHealthContext(
            status="UNAVAILABLE",
            reason=reason,
            pep_person_id=person.pep_person_id,
        )
