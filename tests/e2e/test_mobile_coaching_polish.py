from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "src" / "hwa" / "web" / "static"
TEMPLATES = ROOT / "src" / "hwa" / "web" / "templates"


def test_desktop_and_tablet_navigation_meets_touch_floor() -> None:
    css = (STATIC / "app.css").read_text(encoding="utf-8")

    assert "/* Touch-safe desktop/tablet navigation */" in css
    assert ".primary-nav__item {\n    min-height: 46px;" in css


def test_mobile_feedback_and_rest_are_dedicated_coaching_states() -> None:
    css = (STATIC / "workout.css").read_text(encoding="utf-8")

    assert "/* Mobile dedicated feedback/rest state */" in css
    assert ".workout-player.is-set-feedback .strength-item .strength-coach-grid" in css
    assert ".workout-player.is-resting .strength-item .strength-coach-grid" in css
    assert "display: none;" in css
    assert ".workout-player.is-set-feedback .workout-command-bar" in css
    assert ".workout-player.is-resting .workout-command-bar" in css
    assert ".workout-sidebar" in css


def test_rest_state_has_mockup_style_controls() -> None:
    workout = (TEMPLATES / "workout.html").read_text(encoding="utf-8")
    script = (STATIC / "workout.js").read_text(encoding="utf-8")

    assert 'data-add-rest' in workout
    assert "+15 sec" in workout
    assert 'data-end-rest' in workout
    assert "Skip Rest" in workout
    assert "function addRestTime" in script
    assert "restRemaining += 15" in script


def test_mobile_shell_reserves_space_for_fixed_navigation() -> None:
    css = (STATIC / "app.css").read_text(encoding="utf-8")

    assert "/* Reserve space for the fixed mobile product nav */" in css
    assert "padding-bottom: 7.5rem;" in css
