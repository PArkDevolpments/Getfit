# Getfit UI/UX Evolution Workstream Catalogue

Workstream IDs are stable programme references. GitHub issue numbers are tracked in `PROGRAMME_LEDGER.md`.

## 0.1.40 — Quality foundation

### GF-0140-01 — Review-pack visibility correctness

Make automated/UI review evidence count only genuinely visible and reachable elements. Hidden DOM, inactive controls and screen-reader-only review text must not satisfy visual acceptance.

### GF-0140-02 — Review-pack privacy sanitisation

Remove Home Assistant ingress/session identifiers, unnecessary internal IDs and unsafe implementation details from shareable review artifacts.

### GF-0140-03 — Mobile workout secondary controls

Make Previous, Pause, Skip and Stop genuinely visible/reachable on mobile without weakening Complete Set hierarchy.

### GF-0140-04 — Today responsive contract alignment

Resolve the mismatch between mobile Today and the accepted product contract. Preserve useful workout, weekly and recent-training context without creating clutter.

### GF-0140-05 — Accessibility contrast closure

Close remaining low-contrast states across Today, Plan, Progress, cardio and shared chrome.

### GF-0140-06 — Tablet review-capture reliability

Repair tablet review capture so 820px evidence is trustworthy and no fixed-nav/foreignObject corruption masks real UI behaviour.

## 0.2.0 — Core premium journey

### GF-0200-01 — Shared design system

Create/reconcile design tokens and reusable primitives such as PageHeader, WorkoutHero, MetricTile, ProgressBar, StatusPill, CoachInsight, PreviousPerformance, ExerciseMedia, NumberStepper, EffortPicker, WorkoutActionTray, ChartCard, PRCard, WeekTimeline and EmptyState.

### GF-0200-02 — Today coaching dashboard

Implement the premium Today experience: next-workout hero, Start/Resume, next target/reason, weekly progress, weekly timeline and last-workout summary.

### GF-0200-03 — Live workout coaching context

Add previous comparable performance and explainable coach context to the existing workout player while preserving current logging flow.

### GF-0200-04 — Workout Complete

Create the evidence-backed completion summary, PR and coach-adjustment experience after atomic completion.

### GF-0200-05 — Progress information architecture

Introduce Strength, Training, Muscles and Consistency modes without duplicating Pep Health interpretation.

### GF-0200-06 — Strength analytics presentation

Improve exercise progress charts, metric/time-range controls and best/current summaries using effective Getfit evidence.

### GF-0200-07 — Muscle activity visualisation

Add front/back descriptive muscle-exposure visualisation based on Getfit training evidence.

### GF-0200-08 — Training and consistency presentation

Improve planned/completed session consistency and useful training analytics without vanity metrics.

### GF-0200-09 — Responsive premium pass

Design and verify compact phone, large phone, tablet and desktop compositions for all 0.2.0 surfaces.

### GF-0200-10 — 0.2.0 release validation

Run full architecture, domain, QA, accessibility, visual, privacy and production-release gates.

## 0.2.1 — Programme and discovery

### GF-0210-01 — Plan journey

Present programme phases/blocks and current-week state as an understandable 52-week journey.

### GF-0210-02 — Library density and discovery

Increase scan density, search/filter usability and consistency while retaining the governed local exercise catalogue.

### GF-0210-03 — Exercise Detail

Unify Technique, History and Progress around canonical exercise identity.

### GF-0210-04 — More information architecture

Reorganise secondary functions into Training, Connected, Your Data and Getfit sections.

### GF-0210-05 — 0.2.1 release validation

Run full release gates for Plan/Library/Exercise Detail/More evolution.

## 0.2.2 — Polish and ambient experience

### GF-0220-01 — Workout dark mode

Add Light/Dark/Follow system treatment, prioritising active workout, rest and cardio.

### GF-0220-02 — Motion system

Add restrained state-transition motion with reduced-motion support.

### GF-0220-03 — Home Assistant ambient surfaces

Design and implement appropriate Getfit HA dashboard/card/optional notification surfaces without changing evidence authority.

### GF-0220-04 — 0.2.2 release validation

Run full release gates for dark mode, motion and HA ambient surfaces.

## Future 0.3.x — Coaching engine

Do not pull this work into 0.1.40/0.2.x without explicit approval.

Future areas:

- pure/pluggable progression policies;
- double progression;
- evidence-based target proposals;
- approved exercise substitution;
- missed-workout/schedule handling;
- shortened-session mode;
- warm-up logic;
- advanced set types.

Progression must be person-scoped, explainable, history-preserving and fail safe when evidence is insufficient.
