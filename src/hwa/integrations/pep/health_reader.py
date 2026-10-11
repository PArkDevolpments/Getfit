"""Typed, fail-closed reader for Pep-Site Health Context v1."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime
from typing import Annotated, Literal, Protocol

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictStr,
    ValidationError,
    field_validator,
)

from hwa.domain.identity import PersonContext
from hwa.integrations.pep.ha_health_service import HaHealthServiceEnvelope, HaHealthServiceFailure

PEP_HEALTH_SCHEMA = "peptide-site.health-context"
PEP_HEALTH_VERSION = 1
PEP_HEALTH_AUTHORITY = "PEPTIDE_SITE_HEALTH"
_GOVERNED_ERRORS = {
    "HEALTH_AUTHORITY_DISABLED": 503,
    "SERVICE_ASSERTION_STARTUP_QUARANTINE": 503,
    "INVALID_SERVICE_ASSERTION": 401,
    "PERSON_CONTEXT_UNAVAILABLE": 403,
    "ASSERTION_RATE_LIMITED": 429,
}


class HealthServiceClient(Protocol):
    async def get_health_context(
        self, assertion: str
    ) -> HaHealthServiceEnvelope | HaHealthServiceFailure: ...


class AssertionSigner(Protocol):
    def sign(self, subject: str) -> str: ...


def _aware_timestamp(value: str) -> str:
    if (
        re.fullmatch(
            r"\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?"
            r"(?:[Zz]|[+-](?:[01]\d|2[0-3]):[0-5]\d)",
            value,
        )
        is None
    ):
        raise ValueError("INVALID_CONTRACT_TIMESTAMP")
    instant = datetime.fromisoformat(value.upper().replace("Z", "+00:00"))
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("INVALID_CONTRACT_TIMESTAMP")
    return value


AwareTimestamp = Annotated[StrictStr, AfterValidator(_aware_timestamp)]


class StrictModel(BaseModel):
    """Closed contract model matching Pep's additionalProperties=false policy."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, populate_by_name=True, allow_inf_nan=False
    )


class PepHealthMetric(StrictModel):
    status: Literal["available", "unavailable"]
    metric: StrictStr = Field(min_length=1)
    value: StrictFloat | None
    unit: StrictStr
    recorded_at: AwareTimestamp | None
    derived: StrictBool
    reason: StrictStr = Field(min_length=1)
    basis: tuple[StrictStr, ...] | None = None


class PepHealthReadiness(StrictModel):
    ready: StrictBool
    state: StrictStr = Field(min_length=1)
    reason: StrictStr = Field(min_length=1)
    usable_observation_count: StrictFloat = Field(ge=0)
    data_quality: StrictStr = Field(min_length=1)


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
    verdict: StrictStr = Field(min_length=1)
    confidence: StrictStr = Field(min_length=1)
    reason: StrictStr = Field(min_length=1)
    flags: tuple[StrictStr, ...]


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
    fat_mass_change_28d_kg: StrictFloat | None
    waist_change_28d_cm: StrictFloat | None
    ffm_change_28d_kg: StrictFloat | None
    total_weight_loss_28d_kg: StrictFloat | None
    ffm_loss_ratio_pct: StrictFloat | None
    body_recomposition: StrictBool | None
    confidence: StrictStr | None
    data_quality: StrictStr | None


class PepHealthDomain(StrictModel):
    domain_id: StrictStr = Field(min_length=1)
    state: StrictStr = Field(min_length=1)
    reason: StrictStr = Field(min_length=1)
    ready: StrictBool
    decision_eligible: StrictBool


class PepHealthProvenance(StrictModel):
    authority: Literal["PEPTIDE_SITE_HEALTH"]
    runtime_version: StrictStr | None


class PepHealthContractV1(StrictModel):
    schema_name: Literal["peptide-site.health-context"] = Field(alias="schema")
    schema_version: Literal[1]
    authority: Literal["PEPTIDE_SITE_HEALTH"]
    exported_at: AwareTimestamp
    person_id: StrictStr | None
    health_profile_id: StrictStr | None
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

    @field_validator("schema_version", mode="before")
    @classmethod
    def _integer_version(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("INVALID_CONTRACT_VERSION")
        return value

    @field_validator("automatic_action", "causation_asserted", mode="before")
    @classmethod
    def _false_only(cls, value: object) -> object:
        if value is not False:
            raise ValueError("INVALID_CONTRACT_AUTHORITY_FLAG")
        return value


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
                instant = datetime.fromisoformat(metric.recorded_at.upper().replace("Z", "+00:00"))
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
        *,
        service_client: HealthServiceClient,
        signer: AssertionSigner,
    ) -> None:
        self._service_client = service_client
        self._signer = signer

    async def read(self, *, ha_user_id: str, person: PersonContext) -> PepHealthContext:
        if not isinstance(ha_user_id, str) or not ha_user_id.strip():
            return self._unavailable(person, "PEP_HEALTH_UNAVAILABLE")
        try:
            assertion = self._signer.sign(ha_user_id)
            response = await self._service_client.get_health_context(assertion)
        except Exception:
            # Dependency messages may include credentials or Health/identity data.
            # Cancellation is a BaseException and propagates without retry.
            return self._unavailable(person, "PEP_HEALTH_UNAVAILABLE")

        if (
            not isinstance(response, HaHealthServiceEnvelope)
            or type(response.status_code) is not int
            or not isinstance(response.body, Mapping)
            or not isinstance(response.headers, Mapping)
            or any(
                not isinstance(key, str) or not isinstance(value, str)
                for key, value in response.headers.items()
            )
            or response.headers.get("Cache-Control") != "no-store"
        ):
            return self._unavailable(person, "PEP_HEALTH_UNAVAILABLE")
        if response.status_code != 200:
            error = response.body.get("error")
            reason = (
                error
                if isinstance(error, str) and _GOVERNED_ERRORS.get(error) == response.status_code
                else "PEP_HEALTH_UNAVAILABLE"
            )
            return self._unavailable(person, reason)

        payload = response.body
        if (
            payload.get("schema") != PEP_HEALTH_SCHEMA
            or type(payload.get("schema_version")) is not int
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
