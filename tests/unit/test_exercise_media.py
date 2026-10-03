from pathlib import Path

from hwa.domain.exercise_media import ExerciseMedia, resolve_exercise_media

MEDIA_ROOT = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "hwa"
    / "web"
    / "static"
    / "media"
    / "exercises"
)


def test_missing_media_is_non_blocking() -> None:
    media = resolve_exercise_media("unknown-exercise")
    assert media.exercise_id == "unknown-exercise"
    assert media.available is False
    assert media.local_demo_path is None
    assert media.local_video_path is None


def test_week_one_exercises_are_local_only() -> None:
    exercise_ids = (
        "dumbbell_floor_press",
        "one_arm_dumbbell_row",
        "seated_dumbbell_shoulder_press",
        "dumbbell_biceps_curl",
        "overhead_triceps_extension",
        "goblet_squat",
        "dumbbell_romanian_deadlift",
        "supported_reverse_lunge",
        "standing_calf_raise",
        "dead_bug",
        "forearm_plank",
        "dumbbell_lateral_raise",
        "hammer_curl",
    )

    for exercise_id in exercise_ids:
        media = resolve_exercise_media(exercise_id)
        assert media.local_video_filename == f"{exercise_id}.mp4"
        assert media.local_video_path == f"/exercise-videos/{exercise_id}.mp4"
        assert media.available is True


def test_approved_exercise_media_uses_local_photorealistic_raster_assets() -> None:
    exercise_ids = (
        "dumbbell_floor_press",
        "one_arm_dumbbell_row",
        "seated_dumbbell_shoulder_press",
        "dumbbell_biceps_curl",
        "overhead_triceps_extension",
        "goblet_squat",
        "dumbbell_romanian_deadlift",
        "supported_reverse_lunge",
        "standing_calf_raise",
        "dead_bug",
        "forearm_plank",
        "dumbbell_lateral_raise",
        "hammer_curl",
    )
    for exercise_id in exercise_ids:
        media = (MEDIA_ROOT / f"{exercise_id}.svg").read_text(encoding="utf-8")
        assert "data:image/webp;base64," in media
        assert "<path" not in media
        assert "<circle" not in media


def test_three_stage_technique_media_is_photorealistic_and_local() -> None:
    phased = ("dumbbell_floor_press", "goblet_squat", "dumbbell_romanian_deadlift")
    for exercise_id in phased:
        for phase in ("start", "lower", "drive"):
            media = (MEDIA_ROOT / "phases" / f"{exercise_id}-{phase}.svg").read_text(
                encoding="utf-8"
            )
            assert "data:image/webp;base64," in media
            assert "<path" not in media
            assert "<circle" not in media


def test_local_video_filename_rejects_path_traversal() -> None:
    media = ExerciseMedia(
        exercise_id="unsafe",
        local_video_filename="../unsafe.mp4",
    )
    assert media.local_video_path is None
