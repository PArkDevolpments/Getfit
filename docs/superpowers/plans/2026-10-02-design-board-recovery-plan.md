# Getfit design-board recovery plan

Date: 2026-10-02
Authority: approved Home Workout Assistant design board + Workout Schedule Plan project sources.
Baseline: production 0.1.3 / main `0cdf72b5e0bd0ff671b2227bc9da00f7e68e5086`.

## Goal

Replace the generic 0.1.3 presentation with a screen-by-screen implementation of the approved product design while preserving the working Getfit backend, trusted Home Assistant identity, drafts, resume, history and Pep export.

The design gate is no longer "dark theme + responsive + tests green". Each gate must render the information hierarchy shown on the approved board and be human-reviewed in live Home Assistant before the next visual workstream is released.

## Working rules

- Existing backend authority remains authoritative.
- UI values must bind to programme/person/workout evidence where they exist.
- Example numbers from the design board are used only where they are explicitly approved presentation metadata; performed evidence is never invented.
- Missing person-specific loads remain calibration/unassigned rather than being guessed.
- Spin bike never exposes incline or speed.
- Treadmill never exposes bike cadence/resistance.
- No Weeks 2–52 are fabricated.
- Every release must pass exact-head CI and production multi-arch image verification before Home Assistant update.
- Each human gate is PASS / FAIL. A FAIL is corrected before starting the next gate.

## Gate 1 — Home dashboard + workout selection

Target release: 0.1.4

Implement board sections 4 and 5:

- per-person accent treatment driven by trusted profile presentation, not a browser selector
- greeting and signed-in identity
- Next Workout card with Week/Day, title and approved Week 1 duration range
- prominent Start / Resume action
- four "This week" completion indicators
- last completed workout summary
- current prescription snapshot using real person-specific programme overrides
- weekly cardio minutes derived from completed workout evidence against the board's 150-minute goal
- four polished Week 1 workout-selection rows with icons, type and duration
- weekly goal card
- desktop/tablet/mobile rendering matching the board's light-card-on-navy hierarchy

Human live gate:
1. Open Today in HA mobile app.
2. Open Today on tablet/desktop.
3. Confirm identity/person accent is correct.
4. Confirm Week 1 Day 1 title/data and person-specific prescription values are correct.
5. Confirm no internal IDs/debug copy are visible.
6. PASS or FAIL the visual hierarchy against board sections 4 and 5.

## Gate 2 — Strength workout + set-complete coaching

Target release: next patch after Gate 1 PASS.

Implement board sections 6 and 7:

- movement demo area as the dominant visual
- current exercise, exercise count and workout progress
- reps / prescribed load / tempo as three primary metrics
- one current set rather than a wall of form fields
- Complete Set primary action
- dedicated feedback state: Too easy / About right / Too hard / Pain-Stop
- rest countdown state
- explicit next set / next exercise
- Technique entry point
- Previous / Pause / Skip / Next / Stop retained as secondary workout controls
- actual load, RPE/RIR recorded without making the screen look like a database form

Human live gate:
perform Day 1 Floor Press Set 1 through set completion/rest and PASS or FAIL against board section 6.

## Gate 3 — Exercise demonstration + media

Implement board section 7:

- local visual demonstration sequence
- Start / movement / finish frames where an approved local asset exists
- technique checklist
- Images / Technique / Video hierarchy
- approved external technique video only where configured
- robust media-unavailable fallback which still looks intentional

Human live gate:
open Floor Press, Goblet Squat and RDL technique views on phone/tablet and PASS or FAIL.

## Gate 4 — Cardio + intervals

Implement board sections 8 and 9:

- dedicated spin-bike display: timer, cadence, resistance, RPE; no incline/speed
- dedicated treadmill display: timer, speed, incline, RPE
- high-intensity interval state with red treatment, round number, huge countdown and next recovery
- automatic recovery transition presentation without auto-advancing strength work
- target and actual fields visually separated

Human live gate:
run Day 1 bike and Day 4 hard/recovery interval states, then PASS or FAIL.

## Gate 5 — Progress

Implement board section 10:

- actual per-exercise progression chart from performed evidence
- recent-session progression table
- programme completion
- completed sessions
- no fake trend points or future weeks
- person-scoped history only

Human live gate:
open Progress after recorded workouts and PASS or FAIL the chart/data usefulness.

## Gate 6 — Library, Settings and optional smart-home surface

Implement remaining product surfaces:

- Library cards using real local media where available
- technique cues, muscle/body-area context and personal exercise history
- Settings kept product-like and safe
- equipment capability detail
- Pep Health and Menu-Nutrition status
- smart-home features shown only when actually configured; no fabricated state

Human live gate:
review Library + Settings + configured integration states.

## Final gate — 0.2.0 product acceptance

- screenshot-based browser regression set at phone/tablet/desktop breakpoints
- visual review against the approved board
- full functional regression
- restart/resume
- workout history
- Pep export
- Home Assistant Ingress assets/navigation/API
- amd64/aarch64 public production image verification

0.1.3 remains the rollback point until the staged design-board recovery has passed.
