"""Explainable person-scoped strength progression decisions.

Progression is deliberately rule-driven. No demographic formula, bodyweight rule,
or inferred increment is permitted here: an explicit approved rule and sufficient
performed evidence are required before a target change can be proposed.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class ProgressionAction(StrEnum):
    PROPOSE_CHANGE = "PROPOSE_CHANGE"
    HOLD_TARGET = "HOLD_TARGET"
    CALIBRATION_REQUIRED = "CALIBRATION_REQUIRED"


@dataclass(frozen=True, slots=True)
class ProgressionEvidence:
    person_id: str
    event_id: str
    revision_number: int
    completed_sets: int
    total_sets: int
    minimum_reps: int | None
    maximum_rpe: Decimal | None
    minimum_rir: int | None
    pain_flagged: bool


@dataclass(frozen=True, slots=True)
class ProgressionRule:
    rule_id: str
    required_completed_sessions: int
    minimum_reps_per_set: int
    maximum_rpe: Decimal
    minimum_rir: int
    load_increment: Decimal
    load_unit: str

    def __post_init__(self) -> None:
        if self.required_completed_sessions <= 0:
            raise ValueError("required_completed_sessions must be positive")
        if self.minimum_reps_per_set <= 0:
            raise ValueError("minimum_reps_per_set must be positive")
        if self.maximum_rpe <= 0:
            raise ValueError("maximum_rpe must be positive")
        if self.minimum_rir < 0:
            raise ValueError("minimum_rir cannot be negative")
        if self.load_increment <= 0:
            raise ValueError("load_increment must be positive")
        if not self.load_unit.strip():
            raise ValueError("load_unit is required")


@dataclass(frozen=True, slots=True)
class ProgressionDecision:
    person_id: str
    exercise_id: str
    action: ProgressionAction
    current_load: Decimal | None
    current_load_unit: str | None
    proposed_load: Decimal | None
    proposed_load_unit: str | None
    rule_id: str | None
    evidence_refs: tuple[ProgressionEvidence, ...]
    reason: str


def _decision(
    *,
    person_id: str,
    exercise_id: str,
    action: ProgressionAction,
    current_load: Decimal | None,
    current_load_unit: str | None,
    proposed_load: Decimal | None = None,
    proposed_load_unit: str | None = None,
    rule_id: str | None = None,
    evidence_refs: tuple[ProgressionEvidence, ...] = (),
    reason: str,
) -> ProgressionDecision:
    return ProgressionDecision(
        person_id=person_id,
        exercise_id=exercise_id,
        action=action,
        current_load=current_load,
        current_load_unit=current_load_unit,
        proposed_load=proposed_load,
        proposed_load_unit=proposed_load_unit,
        rule_id=rule_id,
        evidence_refs=evidence_refs,
        reason=reason,
    )


def _evidence_meets_rule(item: ProgressionEvidence, rule: ProgressionRule) -> bool:
    if item.completed_sets != item.total_sets or item.total_sets <= 0:
        return False
    if item.minimum_reps is None or item.minimum_reps < rule.minimum_reps_per_set:
        return False
    if item.maximum_rpe is None or item.maximum_rpe > rule.maximum_rpe:
        return False
    if item.minimum_rir is None or item.minimum_rir < rule.minimum_rir:
        return False
    if item.pain_flagged:
        return False
    return True


def decide_strength_progression(
    *,
    person_id: str,
    exercise_id: str,
    current_load: Decimal | None,
    current_load_unit: str | None,
    evidence: tuple[ProgressionEvidence, ...],
    rule: ProgressionRule | None,
) -> ProgressionDecision:
    """Decide whether an approved rule is satisfied by performed evidence.

    The function never persists a target and never manufactures a rule. A caller may
    present a proposal to the user or a later approval workflow, but this decision does
    not rewrite prescription or completed history.
    """

    if any(item.person_id != person_id for item in evidence):
        return _decision(
            person_id=person_id,
            exercise_id=exercise_id,
            action=ProgressionAction.CALIBRATION_REQUIRED,
            current_load=current_load,
            current_load_unit=current_load_unit,
            reason="Evidence belongs to a different person; cross-person evidence is rejected.",
        )

    if current_load is None or current_load <= 0 or not current_load_unit:
        return _decision(
            person_id=person_id,
            exercise_id=exercise_id,
            action=ProgressionAction.CALIBRATION_REQUIRED,
            current_load=current_load,
            current_load_unit=current_load_unit,
            reason="No valid current target exists; individual calibration is required.",
        )

    if rule is None:
        return _decision(
            person_id=person_id,
            exercise_id=exercise_id,
            action=ProgressionAction.HOLD_TARGET,
            current_load=current_load,
            current_load_unit=current_load_unit,
            reason="No approved progression rule exists; retain the current target.",
        )

    if current_load_unit.upper() != rule.load_unit.upper():
        return _decision(
            person_id=person_id,
            exercise_id=exercise_id,
            action=ProgressionAction.HOLD_TARGET,
            current_load=current_load,
            current_load_unit=current_load_unit,
            rule_id=rule.rule_id,
            reason=(
                "Progression rule load unit does not match the current target; "
                "retain it unchanged."
            ),
        )

    qualifying = tuple(item for item in evidence if _evidence_meets_rule(item, rule))
    required = rule.required_completed_sessions
    if len(qualifying) < required:
        return _decision(
            person_id=person_id,
            exercise_id=exercise_id,
            action=ProgressionAction.HOLD_TARGET,
            current_load=current_load,
            current_load_unit=current_load_unit,
            rule_id=rule.rule_id,
            evidence_refs=qualifying,
            reason=(
                f"Insufficient qualifying performed evidence: {len(qualifying)} of "
                f"{required} required completed sessions meet the approved rule."
            ),
        )

    used = qualifying[:required]
    proposed = current_load + rule.load_increment
    return _decision(
        person_id=person_id,
        exercise_id=exercise_id,
        action=ProgressionAction.PROPOSE_CHANGE,
        current_load=current_load,
        current_load_unit=current_load_unit,
        proposed_load=proposed,
        proposed_load_unit=rule.load_unit,
        rule_id=rule.rule_id,
        evidence_refs=used,
        reason=(
            f"Approved rule {rule.rule_id} is satisfied by {required} completed sessions; "
            f"propose {current_load} {current_load_unit} → {proposed} {rule.load_unit}."
        ),
    )
