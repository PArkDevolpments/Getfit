# Getfit Product Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the approved Getfit/Home Workout Assistant product experience on top of the HWA Foundation, culminating in a person-scoped four-session-per-week 52-week training app whose structured workout records are the authoritative Pep `WORKOUT_EVENT_SOURCE`.

**Architecture:** Keep Getfit as a local-first FastAPI application behind Home Assistant Supervisor Ingress. Programme prescription, drafts, immutable performed-workout revisions and progression remain inside Getfit; Pep Health and Menu-Nutrition are read-only contextual dependencies; Pep receives only the effective person-scoped workout projection. UI work consumes domain services rather than owning training history or authority logic.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, SQLite/WAL, Jinja2, Playwright, pytest, Ruff, mypy, Home Assistant Supervisor Ingress.

**Spec:** `docs/superpowers/specs/2026-09-30-getfit-product-design.md`

## Global Constraints

- Foundation design and `docs/superpowers/plans/2026-09-30-hwa-foundation-implementation.md` remain authoritative prerequisites.
- Getfit/HWA is authoritative for structured workout prescription and performed workout evidence.
- Pep-Site remains authoritative for Health analysis and outcome interpretation.
- Menu-Nutrition remains authoritative for nutrition.
- Health Bridge / Withings / Apple / Home Assistant activity data is supporting context only.
- Never fabricate workouts from steps, exercise minutes, calories, Withings “last workout”, or Apple aggregate workout records.
- Production identity requires trusted Home Assistant Supervisor Ingress plus explicit stable-user mapping.
- Kris and Kirsty remain strictly person scoped with no cross-person fallback.
- Persist instants as UTC and present them in `Europe/London`; reject naive timestamps.
- Active drafts are mutable/resumable; completed and corrected workout revisions are immutable.
- Treadmill supports speed/incline; spin bike supports duration/cadence/resistance and structurally rejects incline.
- RPE is 1.0–10.0; RIR is 0–5.
- Missing physiological evidence remains unavailable rather than estimated.
- Starting loads and progression are individually calibrated from approved targets, performed evidence and feedback; do not derive loads from sex or bodyweight.
- Do not invent missing 52-week prescriptions. Import only approved programme content.
- No LIVE Pep/Home Assistant mutation or automatic Pep Health activation is part of this plan.
- Every implementation task uses RED → observed failure → minimal implementation → focused GREEN → regression suite → commit/review gate.

## Review Focus

1. **Wrong-person state after navigation or resume:** every page/API must resolve the same trusted person before returning drafts, history or targets; permanent E2E coverage belongs to Tasks 1–3 and 5.
2. **Interrupted workout with stale browser state:** the server-side draft and optimistic concurrency token must win; browser recovery coverage belongs to Task 3.
3. **Unapproved or incomplete programme content:** validators must reject a week/day rather than silently generate targets; contract coverage belongs to Task 7.
4. **Downstream Pep/Menu outage:** completed Getfit evidence remains durable and UI degrades without cross-authority fallback; integration coverage belongs to Tasks 8–9.
5. **Correction/export race:** only the effective immutable revision may be projected to Pep, and repeated reads must be deterministic; contract/E2E coverage belongs to Task 8.

---

## Delivery sequence

The HWA Foundation plan is implemented first. This plan begins once the Foundation acceptance gate is green and the canonical domain/persistence interfaces exist. It does not replace Foundation Tasks 2–14.

### Task 1: Product shell and person-safe navigation

**Files:**
- Create: `src/hwa/web/router.py`
- Create: `src/hwa/web/context.py`
- Create: `src/hwa/web/templates/base.html`
- Create: `src/hwa/web/static/app.css`
- Modify: `src/hwa/main.py`
- Test: `tests/integration/web/test_navigation.py`
- Test: `tests/e2e/test_person_isolated_navigation.py`

**Interfaces:**
- Consumes: Foundation trusted identity resolver returning the canonical Getfit person identity.
- Produces: `build_page_context(person, active_nav) -> PageContext` and routes for `/`, `/workout`, `/progress`, `/library`, `/settings`.

- [ ] **Step 1: Write failing navigation/person-isolation tests** asserting the five approved surfaces exist, direct spoofed identity fails, and one person never sees the other person’s context.
- [ ] **Step 2: Run the focused tests** and record the expected missing-route/context failures.
- [ ] **Step 3: Implement the shared page context, base layout and navigation** with no domain authority duplicated in templates.
- [ ] **Step 4: Run focused tests, Ruff and mypy** until green.
- [ ] **Step 5: Commit** as the product-shell change.

### Task 2: Today surface and programme position

**Files:**
- Create: `src/hwa/web/today.py`
- Create: `src/hwa/web/templates/today.html`
- Create: `src/hwa/services/programme_position.py`
- Test: `tests/unit/test_programme_position.py`
- Test: `tests/integration/web/test_today.py`

**Interfaces:**
- Consumes: Foundation programme prescription read model, completed effective workouts and active draft lookup.
- Produces: `get_today_view(person_id, now) -> TodayView` with next/resume state and no fabricated readiness.

- [ ] **Step 1: Write failing tests** for next workout, active-draft resume, completed-day advancement, DST/local-date presentation and missing programme state.
- [ ] **Step 2: Run tests and verify RED.**
- [ ] **Step 3: Implement programme-position service and Today view** so the primary action is Start or Resume and secondary metrics remain subordinate.
- [ ] **Step 4: Run focused plus regression tests.**
- [ ] **Step 5: Commit.**

### Task 3: Guided workout player, autosave and resume

**Files:**
- Create: `src/hwa/web/workout.py`
- Create: `src/hwa/web/templates/workout.html`
- Create: `src/hwa/web/static/workout.js`
- Modify: Foundation draft/application service files created by the Foundation plan.
- Test: `tests/integration/web/test_workout_player.py`
- Test: `tests/e2e/test_workout_resume.py`
- Test: `tests/e2e/test_workout_concurrency.py`

**Interfaces:**
- Consumes: Foundation draft create/read/update, completion and correction services.
- Produces: person-scoped workout-player endpoints supporting set/interval entry, autosave version tokens, resume and completion.

- [ ] **Step 1: Write failing browser/API tests** for reps, timed work, laterality, load mode, RPE/RIR, treadmill fields, spin-bike fields, refresh/resume and stale-write rejection.
- [ ] **Step 2: Verify RED**, including structural rejection of spin-bike incline.
- [ ] **Step 3: Implement the minimal workout player** with server-authoritative draft versions and explicit save feedback.
- [ ] **Step 4: Add completion UI** that creates exactly one immutable Revision 1 under duplicate-submit conditions.
- [ ] **Step 5: Run focused, integration and E2E suites.**
- [ ] **Step 6: Commit.**

### Task 4: Exercise library and technique media

**Files:**
- Create: `src/hwa/domain/exercise_media.py`
- Create: `src/hwa/web/library.py`
- Create: `src/hwa/web/templates/library.html`
- Create: `src/hwa/web/templates/exercise_detail.html`
- Create: `src/hwa/web/static/media.js`
- Test: `tests/unit/test_exercise_media.py`
- Test: `tests/integration/web/test_library.py`

**Interfaces:**
- Consumes: canonical exercise identifiers from Foundation programme data.
- Produces: `ExerciseMedia` metadata with optional local animation/demo and optional approved external video URL.

- [ ] **Step 1: Write failing tests** proving missing media never blocks an exercise/workout and unapproved media URLs are not treated as required programme data.
- [ ] **Step 2: Verify RED.**
- [ ] **Step 3: Implement media metadata and Library/detail views** with local/animated demo as the primary direction and optional approved video embeds.
- [ ] **Step 4: Run focused and browser tests.**
- [ ] **Step 5: Commit.**

### Task 5: Workout history and Progress surface

**Files:**
- Create: `src/hwa/read_models/history.py`
- Create: `src/hwa/read_models/progress.py`
- Create: `src/hwa/web/progress.py`
- Create: `src/hwa/web/templates/progress.html`
- Test: `tests/unit/read_models/test_history.py`
- Test: `tests/unit/read_models/test_progress.py`
- Test: `tests/integration/web/test_progress.py`

**Interfaces:**
- Consumes: only effective completed workout revisions for the resolved person.
- Produces: immutable history rows and descriptive workout-progression summaries; no Pep Health interpretation.

- [ ] **Step 1: Write failing tests** for revision supersession, per-exercise history, adherence/completion history and person isolation.
- [ ] **Step 2: Verify RED.**
- [ ] **Step 3: Implement history/progress read models and the Progress page** without recomputing Pep Health outcomes.
- [ ] **Step 4: Run focused and E2E person-isolation tests.**
- [ ] **Step 5: Commit.**

### Task 6: Individual calibration and explainable progression

**Files:**
- Create: `src/hwa/domain/progression.py`
- Create: `src/hwa/services/progression.py`
- Create: `src/hwa/domain/calibration.py`
- Test: `tests/unit/domain/test_progression.py`
- Test: `tests/unit/domain/test_calibration.py`
- Test: `tests/integration/test_progression_history.py`

**Interfaces:**
- Consumes: approved programme targets plus the person’s effective performed evidence and explicit feedback.
- Produces: `ProgressionDecision` containing proposed target changes, evidence references and reason; historical prescriptions remain unchanged.

- [ ] **Step 1: Write failing tests** proving progression is person scoped, evidence based, explainable and does not use sex/bodyweight as a load calculator.
- [ ] **Step 2: Add tests** for insufficient evidence: retain approved target or require calibration rather than invent a new load/speed/resistance.
- [ ] **Step 3: Verify RED.**
- [ ] **Step 4: Implement calibration/progression policy using only approved rules and captured evidence.**
- [ ] **Step 5: Run unit/integration regressions and commit.**

### Task 7: Approved 52-week programme import and validation

**Files:**
- Create: `src/hwa/programmes/schema.py`
- Create: `src/hwa/programmes/loader.py`
- Create: `src/hwa/programmes/validator.py`
- Create: `data/programmes/README.md`
- Create: `data/programmes/getfit-52-week-v1/` only as approved programme material becomes available.
- Test: `tests/unit/programmes/test_validator.py`
- Test: `tests/contract/test_programme_content.py`

**Interfaces:**
- Consumes: approved programme documents/data only.
- Produces: versioned four-session-per-week programme definitions suitable for Foundation seed/import services.

- [ ] **Step 1: Write failing validation tests** for exactly scoped person-safe programme records, exercise target types, treadmill versus spin-bike equipment rules, and incomplete/unknown fields.
- [ ] **Step 2: Verify RED.**
- [ ] **Step 3: Implement schema/loader/validator** without generating missing workouts or targets.
- [ ] **Step 4: Import Week 1 through the new validator and prove the approved Day 4 structure is unchanged.**
- [ ] **Step 5: Add later approved weeks incrementally; each content batch must pass the same contract suite before commit.**

### Task 8: Authoritative Pep `WORKOUT_EVENT_SOURCE` export

**Files:**
- Create: `src/hwa/integrations/pep/workout_export.py`
- Create: `src/hwa/integrations/pep/schemas.py`
- Create: `src/hwa/api/pep_export.py`
- Test: `tests/contract/test_pep_workout_export.py`
- Test: `tests/integration/test_pep_workout_effective_revision.py`

**Interfaces:**
- Consumes: effective immutable Getfit workout revisions only.
- Produces: deterministic person-scoped read projection carrying stable event/provenance identity, duration and structured effort needed for Pep binding.

- [ ] **Step 1: Write RED contract tests with the current Pep consumer contract in hand**; do not guess unresolved Pep field semantics.
- [ ] **Step 2: Pin the approved Pep duration/effort translation** once the real binding contract is explicit, then keep that mapping versioned.
- [ ] **Step 3: Implement read-only export with identity/provenance/revision enforcement and idempotent output.**
- [ ] **Step 4: Test correction races, repeated reads, outage behavior and wrong-person requests.**
- [ ] **Step 5: Run Getfit contract/E2E suites plus Pep-side RED→GREEN integration QA before any Pep activation.**
- [ ] **Step 6: Commit; activation remains a separate human governance step.**

### Task 9: Read-only Pep Health and Menu-Nutrition context

**Files:**
- Create: `src/hwa/integrations/pep/health_reader.py`
- Create: `src/hwa/integrations/menu/reader.py`
- Create: `src/hwa/domain/external_context.py`
- Modify: `src/hwa/web/today.py`
- Test: `tests/contract/test_pep_health_reader.py`
- Test: `tests/contract/test_menu_reader.py`
- Test: `tests/integration/web/test_context_degradation.py`

**Interfaces:**
- Consumes: approved typed person-scoped read contracts from Pep Health and Menu-Nutrition.
- Produces: optional contextual `ExternalContext` values for presentation only; never mutation authority.

- [ ] **Step 1: Write failing tests** for wrong-person payloads, unavailable systems, stale/invalid schemas and absence of fallback authority.
- [ ] **Step 2: Verify RED.**
- [ ] **Step 3: Implement fail-closed read adapters and graceful UI degradation.**
- [ ] **Step 4: Run contract/browser regressions and commit.**

### Task 10: Settings, equipment and integration state

**Files:**
- Create: `src/hwa/web/settings.py`
- Create: `src/hwa/web/templates/settings.html`
- Create: `src/hwa/domain/equipment.py`
- Test: `tests/unit/domain/test_equipment.py`
- Test: `tests/integration/web/test_settings.py`

**Interfaces:**
- Consumes: authenticated person context and installation-level integration configuration.
- Produces: explicit equipment/calibration/integration status without exposing another person’s settings or secrets.

- [ ] **Step 1: Write failing tests** for equipment validation, treadmill incline capability, spin-bike no-incline rule and cross-person isolation.
- [ ] **Step 2: Verify RED.**
- [ ] **Step 3: Implement Settings UI/domain validation** without turning display names into identity keys.
- [ ] **Step 4: Run tests and commit.**

### Task 11: Home Assistant ingress packaging and operational recovery

**Files:**
- Create/modify the add-on/package metadata chosen by the Foundation deployment task.
- Create: `docs/operations/home-assistant.md`
- Create: `tests/e2e/test_ingress_identity.py`
- Create: `tests/e2e/test_restart_resume.py`

**Interfaces:**
- Consumes: production trusted-ingress identity provider, SQLite migration boot path and draft persistence.
- Produces: repeatable local deployment where restart/update preserves database state and active drafts.

- [ ] **Step 1: Write/extend ingress and restart recovery tests.**
- [ ] **Step 2: Verify direct spoofed identity remains rejected.**
- [ ] **Step 3: Package the app for the approved Home Assistant runtime and document backup/upgrade/recovery.**
- [ ] **Step 4: Verify migrations plus active-draft resume across a restart.**
- [ ] **Step 5: Commit.**

### Task 12: Whole-product browser and release acceptance

**Files:**
- Create: `tests/e2e/test_full_training_journey.py`
- Create: `tests/e2e/test_kirsty_isolation.py`
- Create: `tests/e2e/test_corrections_and_export.py`
- Create: `tests/e2e/test_responsive_touch.py`
- Modify: `.github/workflows/ci.yml` or the Foundation-equivalent workflow.
- Create: `docs/operations/release-gate.md`

**Interfaces:**
- Consumes: the complete product stack.
- Produces: permanent release evidence that the app works end to end without breaking authority or person boundaries.

- [ ] **Step 1: Add an end-to-end Kris journey**: Today → start → enter strength/cardio evidence → interrupt/resume → complete → history/progress → Pep export.
- [ ] **Step 2: Add a separate Kirsty journey** proving targets/history/drafts never fall back to Kris.
- [ ] **Step 3: Add correction/export coverage** proving only the later effective revision is exported.
- [ ] **Step 4: Add responsive/mobile touch coverage** for the five primary surfaces and live workout controls.
- [ ] **Step 5: Add degraded dependency journeys** for Pep/Menu/media/sensor unavailability without workout-data loss.
- [ ] **Step 6: Run from a clean checkout:** `uv sync --dev`, `uv run ruff check .`, `uv run mypy src`, all unit/integration/contract/E2E pytest suites, Alembic upgrade, then branch CI.
- [ ] **Step 7: Commit and require exact-head green evidence before merge.**

## Product completion gate

Getfit is product-complete for this plan only when:

- Foundation acceptance is green;
- the five approved primary surfaces are usable and person safe;
- active workouts autosave/resume without creating false history;
- completed/corrected evidence is immutable and revision aware;
- four-session-per-week 52-week content present in the repo is approved and contract-valid rather than generated to fill gaps;
- individual progression is evidence based and explainable;
- Pep consumes real Getfit workout events through `WORKOUT_EVENT_SOURCE` without aggregate fallback;
- Pep Health/Menu context remains read-only and fails closed;
- Home Assistant ingress identity is proven in production-shaped tests;
- cross-person isolation, restart recovery, browser workflow and responsive/touch acceptance are permanent QA;
- no LIVE Pep Health activation or authority change has occurred without its separate explicit governance approval.
