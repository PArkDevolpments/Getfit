from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "src/hwa/web/templates"
STATIC = ROOT / "src/hwa/web/static"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_shared_shell_has_premium_design_tokens_and_responsive_navigation() -> None:
    base = _text(TEMPLATES / "base.html")
    css = _text(STATIC / "app.css")

    assert 'class="brand-mark"' in base
    assert 'class="app-header__person"' in base
    assert 'class="primary-nav__icon"' in base
    for token in (
        "--colour-bg:",
        "--colour-surface:",
        "--colour-accent:",
        "--colour-text:",
        "--radius-card:",
        "--shadow-card:",
    ):
        assert token in css
    assert "backdrop-filter" in css
    assert "@media (max-width: 700px)" in css
    assert "position: fixed" in css
    assert "min-height: 48px" in css


def test_today_matches_design_board_home_and_workout_selection_hierarchy() -> None:
    today = _text(TEMPLATES / "foundation.html")
    css = _text(STATIC / "app.css")

    for marker in (
        'class="home-dashboard"',
        'class="next-workout-card"',
        'class="week-status-dots"',
        'class="prescription-snapshot"',
        'class="weekly-cardio"',
        'class="workout-selection"',
        'class="weekly-goal"',
    ):
        assert marker in today

    assert "Progress snapshot" in today
    assert "Weekly cardio" in today
    assert "150 minutes of moderate activity" in today
    assert "progress-orb" not in today
    assert "--board-panel:" in css
    assert "--profile-accent:" in css
    assert 'body[data-profile="female"]' in css


def test_workout_has_guided_stage_hierarchy_and_large_live_controls() -> None:
    workout = _text(TEMPLATES / "workout.html")
    js = _text(STATIC / "workout.js")
    css = _text(STATIC / "workout.css")

    assert 'class="workout-stage' in workout
    assert 'id="workout-progress-bar"' in workout
    assert 'id="rest-timer"' in workout
    for control in ("previous-stage", "pause-workout", "skip-stage", "next-stage", "stop-workout"):
        assert f'id="{control}"' in workout
    assert "setActiveStage" in js
    assert "startRestTimer" in js
    assert ".workout-command-bar" in css
    assert "min-height: 48px" in css


def test_library_and_progress_hide_implementation_ids_and_use_product_cards() -> None:
    library = _text(TEMPLATES / "library.html")
    detail = _text(TEMPLATES / "exercise_detail.html")
    progress = _text(TEMPLATES / "progress.html")

    assert "<code>{{ exercise.exercise_id }}</code>" not in library
    assert "<code>{{ exercise.exercise_id }}</code>" not in detail
    assert 'class="exercise-card' in library
    assert 'class="progress-kpi-grid' in progress
    assert 'class="history-timeline' in progress


def test_settings_uses_safe_status_cards() -> None:
    settings = _text(TEMPLATES / "settings.html")

    assert 'class="settings-grid' in settings
    assert 'class="equipment-card' in settings
    assert 'class="integration-card' in settings
