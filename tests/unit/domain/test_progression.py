from decimal import Decimal

from hwa.domain.progression import (
    ProgressionAction,
    ProgressionEvidence,
    ProgressionRule,
    decide_strength_progression,
)


def _evidence(event_id: str, *, person_id: str = "hwa-kris") -> ProgressionEvidence:
    return ProgressionEvidence(
        person_id=person_id,
        event_id=event_id,
        revision_number=1,
        completed_sets=3,
        total_sets=3,
        minimum_reps=10,
        maximum_rpe=Decimal("8.0"),
        minimum_rir=2,
        pain_flagged=False,
    )


def test_explicit_approved_rule_can_propose_explainable_change() -> None:
    decision = decide_strength_progression(
        person_id="hwa-kris",
        exercise_id="goblet-squat",
        current_load=Decimal("10.0"),
        current_load_unit="KG",
        evidence=(_evidence("event-1"), _evidence("event-2")),
        rule=ProgressionRule(
            rule_id="approved-double-progression-v1",
            required_completed_sessions=2,
            minimum_reps_per_set=10,
            maximum_rpe=Decimal("8.0"),
            minimum_rir=2,
            load_increment=Decimal("2.0"),
            load_unit="KG",
        ),
    )

    assert decision.action is ProgressionAction.PROPOSE_CHANGE
    assert decision.proposed_load == Decimal("12.0")
    assert decision.rule_id == "approved-double-progression-v1"
    assert [ref.event_id for ref in decision.evidence_refs] == ["event-1", "event-2"]
    assert "2 completed sessions" in decision.reason


def test_insufficient_evidence_holds_current_target_instead_of_guessing() -> None:
    decision = decide_strength_progression(
        person_id="hwa-kris",
        exercise_id="goblet-squat",
        current_load=Decimal("10.0"),
        current_load_unit="KG",
        evidence=(_evidence("event-1"),),
        rule=ProgressionRule(
            rule_id="approved-double-progression-v1",
            required_completed_sessions=2,
            minimum_reps_per_set=10,
            maximum_rpe=Decimal("8.0"),
            minimum_rir=2,
            load_increment=Decimal("2.0"),
            load_unit="KG",
        ),
    )

    assert decision.action is ProgressionAction.HOLD_TARGET
    assert decision.proposed_load is None
    assert "insufficient" in decision.reason.lower()


def test_missing_approved_rule_requires_calibration_not_fabricated_progression() -> None:
    decision = decide_strength_progression(
        person_id="hwa-kris",
        exercise_id="goblet-squat",
        current_load=None,
        current_load_unit=None,
        evidence=(_evidence("event-1"), _evidence("event-2")),
        rule=None,
    )

    assert decision.action is ProgressionAction.CALIBRATION_REQUIRED
    assert decision.proposed_load is None
    assert decision.rule_id is None


def test_other_person_evidence_is_rejected_not_borrowed() -> None:
    decision = decide_strength_progression(
        person_id="hwa-kirsty",
        exercise_id="goblet-squat",
        current_load=Decimal("8.0"),
        current_load_unit="KG",
        evidence=(_evidence("kris-event", person_id="hwa-kris"),),
        rule=ProgressionRule(
            rule_id="approved-double-progression-v1",
            required_completed_sessions=1,
            minimum_reps_per_set=10,
            maximum_rpe=Decimal("8.0"),
            minimum_rir=2,
            load_increment=Decimal("2.0"),
            load_unit="KG",
        ),
    )

    assert decision.action is ProgressionAction.CALIBRATION_REQUIRED
    assert decision.evidence_refs == ()
    assert "person" in decision.reason.lower()
