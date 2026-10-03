from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "src" / "hwa" / "web" / "static"
TEMPLATES = ROOT / "src" / "hwa" / "web" / "templates"


def test_review_capture_pack_is_local_and_collects_all_product_surfaces() -> None:
    template = (TEMPLATES / "review_capture.html").read_text(encoding="utf-8")
    script = (STATIC / "review-capture.js").read_text(encoding="utf-8")

    assert "Run automated specification audit" in template
    assert "Visual pack only" in template
    assert "getDisplayMedia" not in script
    assert "preferCurrentTab" not in script
    assert "contentDocument" in script
    assert "foreignObject" in script
    assert "XMLSerializer" in script
    assert "image/svg+xml" in script
    assert ".svg" in script
    assert "review-gallery.html" in script
    assert "toBlob" not in script
    assert "getContext(" not in script
    assert "createZip" in script
    assert "getfit-ui-review-" in script
    assert "review-manifest.json" in script
    assert "README.txt" in script
    assert "detectPageState" in script
    assert "page_state" in script
    assert "No active workout" in script
    assert "430" in script
    assert "820" in script
    assert "1440" in script

    # The capture utility must not depend on a third-party CDN or upload endpoint.
    assert "https://" not in template
    assert "XMLHttpRequest" not in script


def test_review_pack_runs_automated_spec_checks_before_building_zip() -> None:
    script = (STATIC / "review-capture.js").read_text(encoding="utf-8")
    template = (TEMPLATES / "review_capture.html").read_text(encoding="utf-8")

    assert "Run automated specification audit" in template
    assert "runAutomatedAudit" in script
    assert "evaluateCriterion" in script
    assert "automated-acceptance-results.json" in script
    assert "automated-review-report.html" in script
    assert "REVIEW_REQUIRED" in script
    assert "BLOCKED" in script
    assert "PASS" in script
    assert "FAIL" in script
    assert "buildAutomatedReport" in script
    assert "No manual pass/fail entry is required before the ZIP is created." in template


def test_automated_audit_tracks_current_workout_dom_contracts() -> None:
    script = (STATIC / "review-capture.js").read_text(encoding="utf-8")
    workout = (TEMPLATES / "workout.html").read_text(encoding="utf-8")

    assert "data-main-rest-panel" in workout
    assert "querySelector('[data-main-rest-panel]')" in script
    assert "Dedicated 01:30 rest state" in script
    assert "mainRest && restVisible && /01:30/.test(restText) ? 'PASS' : 'FAIL'" in script
    assert "clipped below the active viewport" in script
    assert "clipped below the phone viewport" not in script
    assert "node.dataset.segmentType === 'CONDITIONING'" in script
    assert r"/RPE\s*7(?:\.0+)?–8(?:\.0+)?/" in script
    assert r"/RPE\s*2(?:\.0+)?–3(?:\.0+)?/" in script


def test_automated_audit_measures_core_touch_targets_across_product_states() -> None:
    script = (STATIC / "review-capture.js").read_text(encoding="utf-8")

    assert "function auditTouchTargets" in script
    assert "rect.height < 44 || rect.width < 44" in script
    assert "'strength-feedback'" in script
    assert "'interval-hard'" in script
    assert "'exercise-detail'" in script
    assert "'.exercise-media-tab'" in script
    assert "'.exercise-card__open'" in script
    assert "'.coach-dashboard-card__settings'" in script
    assert "touchAudit.failures.length ? 'FAIL' : 'PASS'" in script


def test_strength_feedback_and_rest_audit_require_active_viewport_visibility() -> None:
    script = (STATIC / "review-capture.js").read_text(encoding="utf-8")

    assert "function fullyVisible" in script
    assert "const feedbackPanel = documentRef.querySelector('[data-set-feedback-panel]')" in script
    assert "feedbackVisible && feedbackButtons.length === 4" in script
    assert "const restVisible = fullyVisible(mainRest, documentRef, profile)" in script
    assert "mainRest && restVisible && /01:30/.test(restText) ? 'PASS' : 'FAIL'" in script


def test_review_pack_captures_approved_video_states() -> None:
    router = (ROOT / "src" / "hwa" / "web" / "router.py").read_text(encoding="utf-8")
    script = (STATIC / "review-capture.js").read_text(encoding="utf-8")

    for target in (
        "exercise-video-floor-press",
        "exercise-video-supported-reverse-lunge",
        "exercise-video-lateral-raise",
    ):
        assert target in router
        assert target in script

    assert '"media_tab": "video"' in router
    assert "if (target.media_tab)" in script
    assert 'data-media-tab="' in script
    assert "replaceExternalFrameState" in script
    assert "Local exercise video" in script
    assert "youtube-nocookie.com" not in script
    assert "Approved YouTube embed" not in script
