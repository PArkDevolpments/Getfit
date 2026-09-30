from pathlib import Path

import pytest
from pydantic import ValidationError


def _draft_module():
    assert Path("src/hwa/domain/draft.py").exists(), "draft domain contract must exist"
    from hwa.domain import draft

    return draft


def test_draft_snapshot_preserves_server_resume_cursor() -> None:
    draft = _draft_module()
    snapshot = draft.WorkoutDraftSnapshot.model_validate(
        {
            "phase": "ACTIVE_SET",
            "current_item_kind": "STRENGTH",
            "current_sequence": 2,
            "current_set_number": 1,
            "state_data": {
                "exercise_id": "one_arm_dumbbell_row",
                "laterality": "LEFT",
                "reps": 10,
            },
        }
    )

    assert snapshot.phase.value == "ACTIVE_SET"
    assert snapshot.current_item_kind == "STRENGTH"
    assert snapshot.current_sequence == 2
    assert snapshot.current_set_number == 1
    assert snapshot.state_data["exercise_id"] == "one_arm_dumbbell_row"


def test_draft_snapshot_rejects_unknown_phase_and_extra_fields() -> None:
    draft = _draft_module()
    with pytest.raises(ValidationError):
        draft.WorkoutDraftSnapshot.model_validate(
            {"phase": "MADE_UP_PHASE", "unexpected": True}
        )
