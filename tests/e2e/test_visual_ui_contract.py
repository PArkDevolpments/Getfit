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
    assert 'data-set-feedback-panel' in workout
    assert 'data-main-rest-panel' in workout
    assert "Too easy" in workout
    assert "About right" in workout
    assert "Too hard" in workout
    assert "Pain / Stop" in workout
    assert "data-pain-stop-panel" in workout
    assert "data-pain-skip" in workout
    assert "data-pain-end" in workout
    assert "data-feedback-continue" in workout
    assert 'class="set-effort-panel"' in workout
    assert "Technique" in workout
    assert "interval-state-banner--hard" in workout
    assert "interval-state-banner--recovery" in workout
    for control in ("previous-stage", "pause-workout", "skip-stage", "next-stage", "stop-workout"):
        assert f'id="{control}"' in workout
    assert "setActiveStage" in js
    assert "startRestTimer" in js
    assert "showFeedback" in js
    assert "applyFeedback" in js
    assert "feedbackPanelFor" in js
    assert "restPanelFor" in js
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
    assert "exercise.media.phase_demo_paths" in detail
    assert "exercise.media.phase_labels[loop.index0]" in detail
    assert 'data-media-panel="technique"' in detail
    assert 'data-media-panel="video"' in detail
    assert "exercise.media.local_video_path" in detail
    assert 'class="exercise-video-embed"' in detail
    assert 'class="exercise-local-video"' in detail
    assert 'class="exercise-local-video"' in detail
    assert 'data-video-src="{{ ingress_url(request, exercise.media.local_video_path) }}"' in detail
    assert "video source[data-video-src]" in _text(STATIC / "media.js")
    assert "iframe[data-video-src]" not in _text(STATIC / "media.js")
    assert "youtube-nocookie.com" not in detail
    assert 'class="progress-kpi-grid' in progress
    assert 'data-progress-chart' in progress
    assert 'class="recent-progression-list"' in progress
    assert 'class="history-timeline' in progress


def test_settings_uses_safe_status_cards() -> None:
    settings = _text(TEMPLATES / "settings.html")

    assert 'class="settings-grid' in settings
    assert 'class="equipment-card' in settings
    assert 'class="integration-card' in settings


def test_exercise_video_tab_is_player_only() -> None:
    detail = _text(TEMPLATES / "exercise_detail.html")

    assert 'class="exercise-video-embed"' in detail
    assert "Approved technique video" not in detail
    assert "Watch the movement" not in detail
    assert "Source:" not in detail
    assert "Open on YouTube" not in detail


def test_strength_feedback_estimates_are_explicit_and_pain_stops_normal_rest_flow() -> None:
    workout = _text(TEMPLATES / "workout.html")
    script = _text(STATIC / "workout.js")

    assert "RPE 6 · about 4 reps left" in workout
    assert "RPE 8 · about 2 reps left" in workout
    assert "RPE 10 · no reps left" in workout
    assert "data-effort-manual-name" in workout
    assert "data-pain-stop-panel" in workout

    pain_branch = script.split("if (choice === 'pain')", 1)[1].split("const estimates", 1)[0]
    assert "showPainStop(stage)" in pain_branch
    assert "showRest(stage)" not in pain_branch
    assert "const manualEffort = checked" in script
    assert "if (!manualEffort)" in script


def test_settings_exposes_device_diagnostics_but_not_internal_build_tools() -> None:
    settings = _text(TEMPLATES / "settings.html")

    assert "Auto-review this device" in settings
    assert "?device=1&autorun=1" in settings
    assert "Quality & build review tools" not in settings
    assert "Specification & Acceptance" not in settings
    assert "Run review pack" not in settings


def test_home_assistant_mobile_shell_uses_full_ingress_viewport() -> None:
    base = _text(TEMPLATES / "base.html")
    refresh = _text(STATIC / "visual-refresh.css")

    assert "viewport-fit=cover" in base
    assert "Home Assistant mobile shell parity" in refresh
    assert "min-height: 100dvh" in refresh
    assert "padding: 12px 12px 0" in refresh
    assert "left: 8px" in refresh
    assert "right: 8px" in refresh
    assert "bottom: max(8px, env(safe-area-inset-bottom))" in refresh
    assert "padding: 0 0 calc(96px + env(safe-area-inset-bottom))" in refresh


def test_mobile_bottom_navigation_fits_the_home_assistant_screen_edge() -> None:
    refresh = _text(STATIC / "visual-refresh.css")
    workout = _text(STATIC / "workout.css")

    assert "--mobile-nav-content-height: 64px" in refresh
    assert ".primary-nav {" in refresh
    assert "left: 0;" in refresh
    assert "right: 0;" in refresh
    assert "bottom: 0;" in refresh
    assert "width: 100%;" in refresh
    assert "border-radius: 14px 14px 0 0" in refresh
    assert "padding-bottom: var(--mobile-nav-total-height)" in refresh
    assert "var(--mobile-nav-content-height, 64px)" in workout


def test_phone_workout_uses_training_first_mobile_workspace() -> None:
    base = _text(TEMPLATES / "base.html")
    refresh = _text(STATIC / "visual-refresh.css")
    workout = _text(STATIC / "workout.css")

    assert '<meta name="theme-color" content="#061219">' in base
    assert "body[data-active-nav=\"workout\"]:has(#workout-player) .app-header" in refresh
    assert "display: none;" in refresh
    assert "phone workout workspace" in workout
    assert "min-height: 118px" in workout
    assert "position: fixed;" in workout
    assert "var(--mobile-nav-total-height, 64px)" in workout
    assert ".cardio-visual-card {" in workout
    assert "display: none;" in workout
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in workout


def test_0127_locked_design_authority_is_wired_into_the_product_shell() -> None:
    base = _text(TEMPLATES / "base.html")
    context = _text(ROOT / "src" / "hwa" / "web" / "context.py")
    pro = _text(STATIC / "pro-ui.css")
    workout_pro = _text(STATIC / "workout-pro.css")

    assert "/static/pro-ui.css" in base
    assert "/static/workout-pro.css" in base
    assert "/static/ha-shell.js" in base
    for item in (
        'NavigationItem("today", "Today", "/")',
        'NavigationItem("plan", "Plan", "/plan")',
        'NavigationItem("workout", "Workout", "/workout")',
        'NavigationItem("progress", "Progress", "/progress")',
        'NavigationItem("more", "More", "/more")',
    ):
        assert item in context
    assert "--pro-green: #2fbf71;" in pro
    assert "Georgia" in pro
    assert "grid-template-columns: repeat(5,minmax(0,1fr))" in pro
    assert "min-height:132px" in workout_pro
    assert "bottom:calc(var(--mobile-nav-total-height) + 8px)" in workout_pro


def test_0127_home_assistant_mobile_shell_owns_safe_area_and_kiosk_header() -> None:
    shell = _text(STATIC / "ha-shell.js")
    pro = _text(STATIC / "pro-ui.css")

    assert "home-assistant/subscribe-properties" in shell
    assert "handleSafeArea: true" in shell
    assert "kioskMode: narrow" in shell
    assert "home-assistant/properties" in shell
    assert "--ha-safe-bottom" in shell
    assert "home-assistant/unsubscribe-properties" in shell
    assert "var(--ha-safe-top)" in pro
    assert "var(--ha-safe-bottom)" in pro


def test_0127_workout_logging_uses_large_touch_steppers_and_visible_cardio_rpe() -> None:
    workout = _text(TEMPLATES / "workout.html")
    script = _text(STATIC / "workout.js")
    css = _text(STATIC / "workout-pro.css")

    assert "data-stepper" in workout
    assert "data-cardio-rpe-step" in workout
    assert 'name="{{ item.item_id }}-rpe"' in workout
    assert "function stepNumericInput" in script
    assert "min-width:44px" in css
    assert "min-height:44px" in css
    assert ".cardio-rpe-control" in css


def test_0127_plan_and_more_surfaces_exist_without_inventing_rest_days() -> None:
    plan = _text(TEMPLATES / "plan.html")
    more = _text(TEMPLATES / "settings.html")

    assert "Only approved training appears here." in plan
    assert "Recovery / rest day" not in plan
    assert "Exercise Library" in more
    assert "Auto-review this device" in more


def test_0128_phone_cardio_and_plan_close_the_measured_viewport_blockers() -> None:
    pro = _text(STATIC / "pro-ui.css")
    workout_pro = _text(STATIC / "workout-pro.css")
    workout_js = _text(STATIC / "workout.js")

    assert "0.1.28 phone cardio blocker closure" in workout_pro
    assert "min-height: 104px" in workout_pro
    assert "grid-template-columns: minmax(0, 1fr) 142px" in workout_pro
    assert ".workout-player.is-last-stage .workout-summary-controls" in workout_pro
    assert "player.classList.toggle('is-last-stage'" in workout_js

    assert "the phone Plan is a weekly overview" in pro
    assert 'body[data-active-nav="plan"] .plan-note' in pro
    assert "display: none !important;" in pro


def test_0129_mockup_polish_restores_light_contrast_and_active_workout_hierarchy() -> None:
    pro = _text(STATIC / "pro-ui.css")
    workout_pro = _text(STATIC / "workout-pro.css")
    workout = _text(TEMPLATES / "workout.html")

    assert "0.1.29 mockup-alignment polish" in pro
    assert ".progress-hero h2" in pro
    assert ".library-hero h2" in pro
    assert ".exercise-detail-heading h2" in pro
    assert ".settings-grid h2" in pro
    assert "color: #182019 !important;" in pro

    assert "0.1.29 active-workout finish pass" in workout_pro
    assert "min-height: clamp(" in workout_pro
    assert "grid-template-columns: repeat(3,minmax(0,1fr))" in workout_pro
    assert ".cardio-rpe-control" in workout_pro
    assert "background: #fbfaf6 !important;" in workout_pro
    assert "> Technique" in workout


def test_0130_locked_v2_authority_drives_active_strength_and_cardio() -> None:
    authority = _text(ROOT / "docs" / "design" / "2026-10-04-getfit-v2-mobile-authority.md")
    workout = _text(TEMPLATES / "workout.html")
    script = _text(STATIC / "workout.js")
    css = _text(STATIC / "workout-pro.css")

    assert "LOCKED WITH MINOR CHANGES (9/10)" in authority
    assert "Today · Plan · Workout · Progress · More" in authority
    assert "Older Home Workout Assistant Design Board / UX Board" in authority
    assert "historical concept material only" in authority

    for label in ("Easy", "Moderate", "Hard", "Max"):
        assert f">{label}</button>" in workout
    assert "data-effort-preset" in workout
    assert "strength-prescription-line" in workout
    assert "Exact effort / pain" in workout
    assert "data-set-pain" in workout
    assert "applyEffortPreset" in script
    assert "if (preset) showRest(stage)" in script

    assert "cardio-live-actions" in workout
    assert "cardio-prescription-card--prescribed-effort" in workout
    assert "Complete Segment →" in workout
    assert "0.1.30 locked Getfit v2 mobile authority" in css
    assert "width: 184px !important;" in css
    assert "border-radius: 50% !important;" in css
    assert "conic-gradient(" in css
    assert ".workout-player.is-cardio-stage .workout-command-bar" in css
    assert "display: none !important;" in css

    # The v2 override deliberately undoes the detached CTA introduced by earlier iterations.
    assert "position: static !important;" in css
    assert ".strength-primary-metrics" in css
    assert "display: none !important;" in css


def test_0131_real_device_polish_fixes_light_states_and_tall_phone_composition() -> None:
    pro = _text(STATIC / "pro-ui.css")
    workout = _text(STATIC / "workout-pro.css")

    assert "0.1.31 real-device contrast correction" in pro
    assert "radial-gradient(circle, #fffdf8 58%, transparent 59%)" in pro
    assert ".progress-ring strong" in pro

    assert "0.1.31 real-device polish" in workout
    assert 'body[data-active-nav="workout"] .set-entry.is-current-set' in workout
    assert "box-shadow: none !important;" in workout
    assert ".set-feedback-panel," in workout
    assert ".main-rest-panel" in workout
    assert ".pain-stop-panel" in workout
    assert ".interval-next-card" in workout
    assert "@media (max-width: 700px) and (min-height: 900px)" in workout
    assert "calc(100dvh - var(--mobile-nav-total-height) - 118px)" in workout
    assert ".cardio-item:not([hidden])" in workout



def test_0139_visual_evidence_and_accessibility_polish_is_locked() -> None:
    router = _text(ROOT / "src" / "hwa" / "web" / "router.py")
    pro = _text(STATIC / "pro-ui.css")
    sandbox = _text(ROOT / "src" / "hwa" / "web" / "review_sandbox.py")

    assert router.count('"page": build_page_context(person, "more")') >= 3
    assert "0.1.39 visual evidence and accessibility polish" in pro
    assert 'body[data-active-nav="more"] .exercise-coaching-card h3' in pro
    assert 'body[data-active-nav="more"] .cue-list--checks li' in pro
    assert 'body[data-active-nav="progress"] .history-row__metrics span' in pro
    assert 'body[data-active-nav="progress"] .progress-chart text' in pro
    assert "flex-wrap: wrap;" in pro
    assert "overflow-x: visible;" in pro

    assert "ExercisePersonalBest(" in sandbox
    assert "MuscleCoverageRow(" in sandbox
    assert "ActivityDay(" in sandbox
    assert "estimated_1rm_kg=Decimal(\"10.7\")" in sandbox
    assert "for offset in range(84)" in sandbox
