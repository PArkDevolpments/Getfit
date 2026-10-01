from hwa.domain.exercise_media import ExerciseMedia, resolve_exercise_media


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
