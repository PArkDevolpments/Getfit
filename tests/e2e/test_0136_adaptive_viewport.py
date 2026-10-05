from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "src" / "hwa" / "web" / "static"
TEMPLATES = ROOT / "src" / "hwa" / "web" / "templates"


def test_0136_viewport_engine_measures_visual_viewport_without_page_scaling() -> None:
    viewport = (STATIC / "viewport.js").read_text(encoding="utf-8")
    base = (TEMPLATES / "base.html").read_text(encoding="utf-8")
    workout = (STATIC / "workout-pro.css").read_text(encoding="utf-8")
    pro = (STATIC / "pro-ui.css").read_text(encoding="utf-8")

    assert "window.visualViewport" in viewport
    assert "--getfit-viewport-h" in viewport
    assert "--getfit-usable-h" in viewport
    assert "viewportBand" in viewport
    assert "'compact'" in viewport
    assert "'standard'" in viewport
    assert "'tall'" in viewport
    assert "ResizeObserver" in viewport
    assert "transform: scale" not in viewport
    assert "zoom" not in viewport.lower()

    assert "/static/viewport.js" in base
    assert base.index("/static/viewport.js") < base.index("/static/ha-shell.js")
    assert "0.1.36 adaptive visual viewport" in pro
    assert "0.1.36 adaptive-height workout composition" in workout
    assert 'html[data-viewport-band="compact"]' in workout
    assert 'html[data-viewport-band="standard"]' in workout
    assert 'html[data-viewport-band="tall"]' in workout


def test_0136_review_pack_checks_fit_critical_vertical_overflow_and_reports_band() -> None:
    script = (STATIC / "review-capture.js").read_text(encoding="utf-8")

    assert "fitCriticalVerticalOverflow" in script
    assert "root.scrollHeight > root.clientHeight + 4" in script
    assert "Fit-critical workout state needs vertical scrolling" in script
    assert "viewport_band: root.dataset.viewportBand || null" in script
    assert "viewport_engine:" in script
    assert "usable_height:" in script
    assert "nav_height:" in script
