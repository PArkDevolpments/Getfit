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


def test_today_matches_approved_board_as_two_primary_surfaces() -> None:
    today = _text(TEMPLATES / "foundation.html")
    css = _text(STATIC / "app.css")

    for marker in (
        'class="home-dashboard"',
        'class="coach-dashboard-card"',
        'class="next-workout-card"',
        'class="week-status-dots"',
        'class="coach-progress-snapshot"',
        'class="weekly-cardio"',
        'class="workout-selection"',
        'class="weekly-goal"',
        'class="home-context-rail"',
    ):
        assert marker in today

    # The approved board keeps the per-user dashboard as one dark coaching surface,
    # with Workout Selection as the adjacent light surface. 0.1.4 split the dashboard
    # into multiple generic white cards, which is not the board.
    assert 'home-panel--progress' not in today
    assert 'class="profile-badge"' not in today
    assert "Progress Snapshot" in today
    assert 'class="coach-dashboard-card__settings"' in today
    assert 'class="coach-profile-mark"' not in today
    assert "Weekly cardio" in today
    assert "150 minutes of moderate activity" in today
    assert "--coach-card-bg:" in css
    assert "--programme-card-bg:" in css
    assert ".home-dashboard {" in css
    assert "grid-template-columns: minmax(0, 0.92fr) minmax(0, 1.08fr)" in css
    assert "align-items: start" in css
    assert 'body[data-profile="female"]' in css


def test_workout_has_guided_stage_hierarchy_and_large_live_controls() -> None:
    workout = _text(TEMPLATES / "workout.html")
    js = _text(STATIC / "workout.js")
    css = _text(STATIC / "workout.css")

    assert 'class="workout-stage' in workout
    assert 'id="workout-progress-bar"' in workout
    assert 'id="rest-timer"' in workout
    assert 'data-complete-set' in workout
    assert 'id="set-feedback-panel"' in workout
    assert 'id="main-rest-panel"' in workout
    assert "Too easy" in workout
    assert "About right" in workout
    assert "Too hard" in workout
    assert "Pain / Stop" in workout
    assert "View Technique" in workout
    assert "interval-state-banner--hard" in workout
    assert "interval-state-banner--recovery" in workout
    for control in ("previous-stage", "pause-workout", "skip-stage", "next-stage", "stop-workout"):
        assert f'id="{control}"' in workout
    assert "setActiveStage" in js
    assert "startRestTimer" in js
    assert "showFeedback" in js
    assert "applyFeedback" in js
    assert ".workout-command-bar" in css
    assert "min-height: 48px" in css


def test_library_and_progress_hide_implementation_ids_and_use_product_cards() -> None:
    library = _text(TEMPLATES / "library.html")
    detail = _text(TEMPLATES / "exercise_detail.html")
    progress = _text(TEMPLATES / "progress.html")

    assert "<code>{{ exercise.exercise_id }}</code>" not in library
    assert "<code>{{ exercise.exercise_id }}</code>" not in detail
    assert 'class="exercise-card' in library
    assert 'class="exercise-card__media"' in library
    assert 'class="exercise-media-tabs"' in detail
    assert "Start" in detail
    assert "Lower" not in detail  # phase labels are media data, not fabricated template copy
    assert 'data-media-panel="technique"' in detail
    assert 'data-media-panel="video"' in detail
    assert 'class="progress-kpi-grid' in progress
    assert 'data-progress-chart' in progress
    assert 'class="recent-progression-list"' in progress
    assert 'class="history-timeline' in progress


def test_settings_uses_safe_status_cards() -> None:
    settings = _text(TEMPLATES / "settings.html")

    assert 'class="settings-grid' in settings
    assert 'class="equipment-card' in settings
    assert 'class="integration-card' in settings
