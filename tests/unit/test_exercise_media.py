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
    assert media.external_video_url is None


def test_external_video_requires_explicit_approval() -> None:
    media = ExerciseMedia(
        exercise_id="goblet-squat",
        local_demo_path=None,
        external_video_url="https://www.youtube.com/watch?v=example",
        external_video_approved=False,
    )
    assert media.approved_external_video_url is None


def test_approved_external_video_must_be_https() -> None:
    media = ExerciseMedia(
        exercise_id="goblet-squat",
        local_demo_path=None,
        external_video_url="http://example.invalid/demo",
        external_video_approved=True,
    )
    assert media.approved_external_video_url is None


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
