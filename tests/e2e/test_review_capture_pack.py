from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "src" / "hwa" / "web" / "static"
TEMPLATES = ROOT / "src" / "hwa" / "web" / "templates"
SCRIPTS = ROOT / "scripts"
WORKFLOWS = ROOT / ".github" / "workflows"


def test_review_capture_pack_is_local_and_collects_all_product_surfaces() -> None:
    template = (TEMPLATES / "review_capture.html").read_text(encoding="utf-8")
    script = (STATIC / "review-capture.js").read_text(encoding="utf-8")

    assert "Run full responsive audit" in template
    assert "Auto-review this device" in template
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
    assert "Home Assistant target · 440×820" in script
    assert "width: 440, height: 820" in script

    # The capture utility must not depend on a third-party CDN or upload endpoint.
    assert "https://" not in template
    assert "XMLHttpRequest" not in script


def test_review_pack_runs_automated_spec_checks_before_building_zip() -> None:
    script = (STATIC / "review-capture.js").read_text(encoding="utf-8")
    template = (TEMPLATES / "review_capture.html").read_text(encoding="utf-8")

    assert "Run full responsive audit" in template
    assert "Auto-review this device" in template
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
    assert "live targets are clipped below the active viewport" in script
    assert "live target grid is clipped below the active viewport" in script
    assert "function liveCardioTargetsFit" in script
    assert "profile.width > 700" in script
    assert ".cardio-item:not([hidden])" in script
    assert "'bike-finisher': '.cardio-item:not([hidden]) .cardio-prescription-grid'" in script
    assert "'treadmill': '.cardio-item:not([hidden]) .cardio-prescription-grid'" in script
    assert "'interval-hard': '.cardio-item:not([hidden]) .cardio-prescription-grid'" in script
    assert "'interval-recovery': '.cardio-item:not([hidden]) .cardio-prescription-grid'" in script
    assert "clipped below the phone viewport" not in script
    assert "node.dataset.segmentType === 'CONDITIONING'" in script
    assert r"/RPE\s*7(?:\.0+)?–8(?:\.0+)?/" in script
    assert r"/RPE\s*2(?:\.0+)?–3(?:\.0+)?/" in script


def test_automated_audit_measures_core_touch_targets_across_product_states() -> None:
    script = (STATIC / "review-capture.js").read_text(encoding="utf-8")

    assert "function auditTouchTargets" in script
    assert "rect.height < 44 || rect.width < 44" in script
    assert "'strength-feedback'" in script
    assert "'strength-pain'" in script
    assert "'interval-hard'" in script
    assert "'exercise-detail'" in script
    assert "'.exercise-media-tab'" in script
    assert "'.exercise-card__open'" in script
    assert "'.coach-dashboard-card__settings'" in script
    assert "touchAudit.failures.length" in script
    assert "fitCriticalVerticalOverflow" in script


def test_strength_feedback_and_rest_audit_require_active_viewport_visibility() -> None:
    script = (STATIC / "review-capture.js").read_text(encoding="utf-8")

    assert "function fullyVisible" in script
    assert "profile.width > 700" in script
    assert "const feedbackPanel = documentRef.querySelector('[data-set-feedback-panel]')" in script
    assert "feedbackVisible && feedbackButtons.length === 4" in script
    assert "const restVisible = profile.width > 700" in script
    assert "|| fullyVisible(mainRest, documentRef, profile)" in script
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


def test_device_review_uses_actual_home_assistant_viewport_and_can_autorun() -> None:
    template = (TEMPLATES / "review_capture.html").read_text(encoding="utf-8")
    script = (STATIC / "review-capture.js").read_text(encoding="utf-8")

    assert 'id="run-device-audit"' in template
    assert "window.visualViewport?.width" in script
    assert "window.visualViewport?.height" in script
    assert "same-origin-home-assistant-device-dom-vector" in script
    assert "getfit-device-review" in script
    assert "params.get('device') === '1'" in script
    assert "params.get('autorun') === '1'" in script
    assert "waitForHostShellReady" in script
    assert "runCapture([profile], {automated: true, deviceMode: true, hostShell})" in script
    assert "device-layout-diagnostics.json" in script
    assert "capture_kind: 'viewport'" in script
    assert "capture_kind: 'full-page'" in script
    assert "{viewportOnly: true}" in script
    assert "prepareZipDownload" in script
    assert "autoDownload: !deviceMode" in script


def test_device_review_measures_bottom_navigation_against_the_viewport() -> None:
    script = (STATIC / "review-capture.js").read_text(encoding="utf-8")

    assert "BOTTOM_NAV_NOT_VIEWPORT_FIT" in script
    assert "bottom_nav:" in script
    assert "documentRef.querySelector('.primary-nav')" in script
    assert "viewportHeight - navRect.top" in script


def test_device_review_requires_live_cardio_targets_in_the_active_viewport() -> None:
    script = (STATIC / "review-capture.js").read_text(encoding="utf-8")

    for target in ("bike-finisher", "treadmill", "interval-hard", "interval-recovery"):
        assert f"'{target}': '.cardio-item:not([hidden]) .cardio-prescription-grid'" in script


def test_0127_device_review_covers_plan_and_more_surfaces() -> None:
    router = (ROOT / "src" / "hwa" / "web" / "router.py").read_text(encoding="utf-8")
    script = (STATIC / "review-capture.js").read_text(encoding="utf-8")

    assert '{"key": "plan", "label": "Plan", "url": ingress_url(request, "/plan")}' in router
    assert '{"key": "more", "label": "More", "url": ingress_url(request, "/more")}' in router
    assert "if (criterionId.startsWith('SETTINGS-')) return ['more'];" in script
    assert "if (criterionId === 'REGRESSION-06') return ['more'];" in script


def test_0133_real_device_review_verifies_native_home_assistant_full_canvas_handshake() -> None:
    script = (STATIC / "review-capture.js").read_text(encoding="utf-8")

    assert "waitForHostShellReady" in script
    assert "hostShellSnapshot" in script
    assert "HOME_ASSISTANT_FULL_CANVAS_HANDSHAKE_MISSING" in script
    assert "'home-assistant-app-panel'" in script
    assert "'getfit-full-canvas-panel'" in script
    assert "home_assistant_shell: deviceMode ? hostShell : null" in script
    assert "collectDeviceDiagnostics(target, documentRef, profile, hostShell)" in script


def test_0135_review_capture_cannot_mix_target_states_or_overlap_runs() -> None:
    script = (STATIC / "review-capture.js").read_text(encoding="utf-8")

    assert "captureRunning" in script
    assert "A review capture is already running" in script
    assert "__getfit_review_capture" in script
    assert "captureIdentity" in script
    assert "captureIdentityMatches" in script
    assert "waitForTargetIdentity" in script
    assert "Capture integrity check failed" in script
    assert "source_review_state: identity.review_state" in script
    assert "source_media_tab: identity.media_tab" in script
    assert "frame.addEventListener('load', onLoad)" in script



def test_review_pack_includes_machine_readable_rendered_content_for_ai_review() -> None:
    script = (STATIC / "review-capture.js").read_text(encoding="utf-8")

    assert "function collectReviewContent" in script
    assert "documentRef?.body?.innerText" in script
    assert "review-content.json" in script
    assert "getfit-review-content-v1" in script
    assert "AI-REVIEW-GUIDE.txt" in script
    assert "text-only file extractors" in script
    assert "getfit-ui-review-pack-v4" in script
    assert "getfit-device-review-pack-v2" in script


def test_ci_review_pack_adds_browser_rendered_pngs_without_replacing_vector_evidence() -> None:
    generator = (SCRIPTS / "generate_review_pack.py").read_text(encoding="utf-8")

    assert "_enrich_pack_for_ai" in generator
    assert "_rasterise_svg" in generator
    assert "ai-screenshots/" in generator
    assert 'type="png"' in generator
    assert "full_page=True" in generator
    assert "review-content.json" in generator
    assert "vector_source_complete" in generator
    assert "ZIP_DEFLATED" in generator
    assert '{"ha-phone", "desktop"}' in generator


def test_review_pack_workflow_cancels_stale_runs_and_limits_artifact_retention() -> None:
    workflow = (WORKFLOWS / "review-pack.yml").read_text(encoding="utf-8")

    assert "concurrency:" in workflow
    assert "cancel-in-progress: true" in workflow
    assert "retention-days: 1" in workflow

def test_0140_review_capture_exports_visibility_state_as_visual_evidence() -> None:
    script = (STATIC / "review-capture.js").read_text(encoding="utf-8")

    assert "function isScreenReaderOnly" in script
    assert "function elementReviewState" in script
    assert "node.hidden" in script
    assert "node.getAttribute('aria-hidden') === 'true'" in script
    assert "style.pointerEvents === 'none'" in script
    assert "geometry:" in script
    assert "in_viewport:" in script
    assert "fully_in_viewport:" in script
    assert "reachable:" in script
    assert "visual_evidence:" in script
    assert "accessibility_metadata:" in script


def test_0140_hidden_or_inactive_controls_cannot_satisfy_visual_acceptance() -> None:
    script = (STATIC / "review-capture.js").read_text(encoding="utf-8")

    assert "function visuallyPresent" in script
    assert "function reachableControl" in script
    assert "const has = (selector) => visuallyPresent(documentRef, selector, profile)" in script
    assert "documentRef?.body?.innerText" in script
    assert "controlSelectors.every((selector) => reachableControl(" in script
    assert "Complete Set control is visible and reachable" in script
    assert "hidden, inactive or unreachable" in script


def test_0140_review_content_keeps_non_visual_accessibility_metadata_separate() -> None:
    script = (STATIC / "review-capture.js").read_text(encoding="utf-8")

    assert "visual_headings" in script
    assert "visual_controls" in script
    assert "non_visual_headings" in script
    assert "non_visual_controls" in script
    assert "screen_reader_only" in script
    assert "accessible_name" in script

    control_record = script.split(
        "function controlReviewRecord", 1
    )[1].split("function collectReviewContent", 1)[0]
    assert "node.getAttribute('name')" not in control_record
    assert "const domText" in script
    assert ".test(domText)" in script
