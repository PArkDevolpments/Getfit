from importlib import import_module
from pathlib import Path

import pytest
from pydantic import ValidationError


def _workout():
    assert Path("src/hwa/domain/workout.py").exists(), "workout schema must exist"
    return import_module("hwa.domain.workout")


def _programme():
    assert Path("src/hwa/domain/programme.py").exists(), "programme schema must exist"
    return import_module("hwa.domain.programme")


def test_each_hand_and_total_external_load_semantics_are_preserved() -> None:
    module = _workout()
    floor_press = module.StrengthSetEvidence(
        set_number=1,
        laterality="BILATERAL",
        target_type="REPS",
        load_value=6,
        load_unit="KG",
        load_mode="EACH_HAND",
        reps=10,
        rir=2,
        rpe=7,
        completed=True,
        pain_flag=False,
    )
    triceps = floor_press.model_copy(
        update={"load_value": 8, "load_mode": "TOTAL_EXTERNAL"}
    )
    assert float(floor_press.load_value) == 6
    assert float(triceps.load_value) == 8


def test_bodyweight_cannot_acquire_external_kg_value() -> None:
    module = _workout()
    with pytest.raises(ValidationError):
        module.StrengthSetEvidence(
            set_number=1,
            laterality="BILATERAL",
            target_type="REPS",
            load_value=5,
            load_unit="KG",
            load_mode="BODYWEIGHT",
            reps=10,
            completed=True,
            pain_flag=False,
        )


def test_timed_set_is_first_class_and_does_not_become_zero_rep_set() -> None:
    module = _workout()
    plank = module.StrengthSetEvidence(
        set_number=1,
        laterality="BILATERAL",
        target_type="DURATION",
        load_value=None,
        load_unit=None,
        load_mode="BODYWEIGHT",
        duration_seconds=22,
        completed=True,
        pain_flag=False,
    )
    assert plank.duration_seconds == 22
    assert plank.reps is None

    with pytest.raises(ValidationError):
        module.StrengthSetEvidence(
            set_number=1,
            laterality="BILATERAL",
            target_type="DURATION",
            load_mode="BODYWEIGHT",
            reps=0,
            duration_seconds=22,
            completed=True,
            pain_flag=False,
        )


def test_unilateral_asymmetry_is_preserved() -> None:
    module = _workout()
    exercise = module.StrengthExercisePerformance(
        exercise_id="supported_reverse_lunge",
        completed=True,
        sets=[
            {
                "set_number": 1,
                "laterality": "LEFT",
                "target_type": "REPS",
                "load_mode": "BODYWEIGHT",
                "reps": 8,
                "completed": True,
                "pain_flag": False,
            },
            {
                "set_number": 1,
                "laterality": "RIGHT",
                "target_type": "REPS",
                "load_mode": "BODYWEIGHT",
                "reps": 7,
                "completed": True,
                "pain_flag": False,
            },
        ],
    )
    assert [item.reps for item in exercise.sets] == [8, 7]


def test_rir_and_rpe_domains_are_enforced() -> None:
    module = _workout()
    base = {
        "set_number": 1,
        "laterality": "BILATERAL",
        "target_type": "REPS",
        "load_mode": "BODYWEIGHT",
        "reps": 10,
        "completed": True,
        "pain_flag": False,
    }
    with pytest.raises(ValidationError):
        module.StrengthSetEvidence(**base, rir=6)
    with pytest.raises(ValidationError):
        module.StrengthSetEvidence(**base, rpe=0.9)
    valid = module.StrengthSetEvidence(**base, rir=0, rpe=7.5)
    assert valid.rir == 0
    assert valid.rpe == 7.5


def test_programme_target_type_requires_matching_target_fields() -> None:
    module = _programme()
    reps = module.StrengthPrescription(
        sequence=1,
        exercise_id="dumbbell_floor_press",
        target_type="REPS",
        sets_target=2,
        reps_target=10,
        laterality="BILATERAL",
        load_mode="EACH_HAND",
        load_unit="KG",
    )
    assert reps.reps_target == 10

    with pytest.raises(ValidationError):
        module.StrengthPrescription(
            sequence=2,
            exercise_id="forearm_plank",
            target_type="DURATION",
            sets_target=2,
            reps_target=0,
            laterality="BILATERAL",
            load_mode="BODYWEIGHT",
        )
