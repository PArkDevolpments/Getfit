from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "src" / "hwa" / "web" / "static"
TEMPLATES = ROOT / "src" / "hwa" / "web" / "templates"


def test_018_shell_uses_green_light_mockup_refresh() -> None:
    base = (TEMPLATES / "base.html").read_text(encoding="utf-8")
    css = (STATIC / "visual-refresh.css").read_text(encoding="utf-8")

    assert '<h1>Getfit</h1>' in base
    assert "Home Workout Assistant" in base
    assert "/static/visual-refresh.css" in base
    assert "--refresh-green: #22c55e;" in css
    assert "--refresh-canvas: #f3f7f5;" in css
    assert "grid-template-columns: 210px minmax(0, 1fr);" in css
    assert 'body:not([data-active-nav="workout"]) .content' in css


def test_018_today_uses_photographic_workout_tiles() -> None:
    today = (TEMPLATES / "foundation.html").read_text(encoding="utf-8")

    assert 'class="next-workout-card__photo"' in today
    assert 'class="workout-select-row__photo"' in today
    assert "/static/media/exercises/dumbbell_floor_press.svg" in today
    assert "/static/media/exercises/goblet_squat.svg" in today
    assert "/static/media/exercises/dumbbell_romanian_deadlift.svg" in today


def test_018_exercise_detail_resolves_photorealistic_phase_assets() -> None:
    media = (ROOT / "src" / "hwa" / "domain" / "exercise_media.py").read_text(
        encoding="utf-8"
    )

    assert 'f"{root}/phases/{exercise_id}-{phase}.svg"' in media


def test_018_cardio_and_rest_use_local_photographic_media() -> None:
    workout = (TEMPLATES / "workout.html").read_text(encoding="utf-8")

    assert "/static/media/cardio/spin-bike.svg" in workout
    assert "/static/media/cardio/treadmill.svg" in workout
    assert "/static/media/cardio/rest-recovery.svg" in workout
    assert 'class="cardio-visual-photo"' in workout
    assert 'class="rest-state-photo"' in workout


def test_018_refresh_preserves_responsive_touch_and_green_primary_actions() -> None:
    css = (STATIC / "visual-refresh.css").read_text(encoding="utf-8")

    assert "@media (max-width: 700px)" in css
    assert "min-height: 44px;" in css
    assert "background: var(--refresh-green);" in css
    assert ".exercise-phase img" in css
    assert ".progress-chart-card" in css
    assert ".settings-grid" in css
