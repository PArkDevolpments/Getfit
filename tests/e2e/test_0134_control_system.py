from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "src" / "hwa" / "web" / "static"
TEMPLATES = ROOT / "src" / "hwa" / "web" / "templates"


def test_0134_shared_professional_control_system_is_loaded_last() -> None:
    controls = (STATIC / "controls.css").read_text(encoding="utf-8")
    base = (TEMPLATES / "base.html").read_text(encoding="utf-8")
    workout = (TEMPLATES / "workout.html").read_text(encoding="utf-8")

    assert "Getfit 0.1.34 professional interaction system" in controls
    assert "--btn-h-primary: 54px" in controls
    assert ".btn--primary" in controls
    assert ".btn--secondary" in controls
    assert ".btn--ghost" in controls
    assert ".btn--danger" in controls
    assert ".btn--icon" in controls
    assert ":focus-visible" in controls
    assert "@media (prefers-reduced-motion: reduce)" in controls

    assert "/static/controls.css" in base
    assert base.index("/static/controls.css") > base.index("/static/workout-pro.css")
    assert 'class="btn btn--primary btn--block complete-set-button"' in workout
    assert 'class="btn btn--danger danger-action"' in workout
    assert 'class="button-icon"' in workout


def test_0134_device_review_rejects_fit_critical_vertical_overflow() -> None:
    script = (STATIC / "review-capture.js").read_text(encoding="utf-8")

    assert "FIT_CRITICAL_VERTICAL_OVERFLOW" in script
    assert "root.scrollHeight > root.clientHeight + 4" in script
    for state in (
        "strength-active",
        "strength-feedback",
        "strength-pain",
        "strength-rest",
        "bike-finisher",
        "treadmill",
        "interval-hard",
        "interval-recovery",
    ):
        assert f"'{state}'" in script
