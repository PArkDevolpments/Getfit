from hwa.domain.exercise_catalog import exercise_profile, normalise_exercise_id


def test_exercise_catalog_normalises_programme_ids_and_exposes_equipment() -> None:
    assert normalise_exercise_id("goblet-squat") == "goblet_squat"
    profile = exercise_profile("goblet-squat")
    assert profile.equipment == ("Dumbbells",)
    assert profile.primary_muscles == ("quads", "glutes")
    assert "core" in profile.secondary_muscles


def test_exercise_catalog_keeps_unknown_programme_movements_non_authoritative() -> None:
    profile = exercise_profile("future-approved-movement")
    assert profile.body_area == "Programme exercise"
    assert profile.technique_cues == ()
    assert profile.equipment == ()
    assert profile.primary_muscles == ()
