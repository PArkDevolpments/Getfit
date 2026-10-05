# Getfit Engineering Operating Contract

## Status

This file is the repository-level operating contract for substantial Getfit development.

All human contributors, AI agents, subagents and automated implementation workers must read this file before making changes.

Repository state, executable tests, approved specifications and current `origin/main` take precedence over remembered chat context. If an assignment conflicts with this file, stop and resolve the conflict explicitly.

## 1. Mission

Getfit is a local-first training product delivered through Home Assistant.

The product aim is:

> Calm personal trainer + premium fitness app + transparent coaching.

Getfit should help the user understand:

1. what they are doing today;
2. what they need to do now;
3. why a training target was selected;
4. whether their training is progressing.

Product polish must never weaken evidence integrity, identity isolation, workout authority or revision history.

## 2. Source-of-truth hierarchy

When information conflicts, use this order:

1. current `origin/main`;
2. approved architecture/product specifications;
3. executable tests;
4. committed programme/release documentation;
5. current approved implementation plan;
6. PR description;
7. chat context or historical summaries.

Never treat a stale SHA, screenshot, count or conversation summary as current authority without reconciliation.

## 3. Domain boundaries

### Getfit owns

- programme prescription;
- workout plans and programme position;
- workout drafts;
- performed workout evidence;
- set/cardio actuals;
- RPE/RIR evidence;
- pain/stop evidence;
- corrections;
- progression history;
- effective workout revision;
- training recommendations;
- workout completion and history.

### Pep-Site owns

- health interpretation;
- readiness interpretation;
- health outcomes.

### Menu-Nutrition owns

- calories;
- macros;
- nutrition planning.

### Supporting health/activity systems

Health Bridge, Withings, Apple activity and similar sources are supporting measured evidence only. They must never masquerade as authoritative Getfit workout events.

## 4. Identity boundary

Person identity must derive from trusted Home Assistant identity.

Requirements:

- person-scoped reads and writes;
- person-scoped drafts and history;
- person-scoped targets and recommendations;
- fail closed on missing, ambiguous or spoofed identity;
- never cross-person fallback.

Cross-person leakage is a release blocker.

## 5. Training invariants

Programme:

- 52 weeks;
- 4 sessions per week.

Known equipment:

- treadmill with incline;
- spin bike without incline;
- adjustable dumbbells.

Do not introduce impossible equipment semantics. Spin bike must not acquire incline. Treadmill may use incline. Load basis must never silently change from EACH_HAND to total load or another basis.

## 6. Workout lifecycle

Canonical lifecycle:

`plan → mutable person-scoped draft → autosave/resume → immutable completion revision → immutable correction/supersession`

Requirements:

- autosave creates no workout revision;
- first completion is Revision 1;
- revisions are immutable;
- corrections supersede rather than rewrite history;
- stable event identity;
- only the effective revision is exported as current;
- duplicate completion is idempotent;
- stale writes are protected against;
- optional downstream failure must not destroy a successful completion.

Never simplify UI work by bypassing this model.

## 7. Evidence rules

Never fabricate:

- reps;
- load;
- RPE/RIR;
- pain;
- duration;
- PRs;
- volume;
- readiness;
- calories;
- progression;
- completion;
- physiological evidence.

Review/demo fixtures may use deterministic synthetic data, but they must remain isolated from production state and clearly belong to review infrastructure.

## 8. Product design principles

### 8.1 Action before decoration

The user should always understand the primary action.

### 8.2 Explain recommendations

Prefer:

> Increase to 6.5 kg because both working sets reached the top of the prescribed range at acceptable effort.

over:

> AI recommends 6.5 kg.

### 8.3 Preserve the strong workout player

The established live-strength sequence is:

`exercise → target → actual → effort → Complete Set → feedback → rest → next`

Do not casually replace this model.

### 8.4 Calm presentation

Use:

- warm light surfaces;
- high-contrast text;
- restrained green;
- clear spacing;
- meaningful imagery;
- purposeful motion.

Avoid:

- dashboard clutter;
- excessive gamification;
- gratuitous gradients;
- animation for animation's sake;
- metrics without actionability.

### 8.5 Mobile is not compressed desktop

Design explicitly for compact phone, large phone, tablet and desktop.

## 9. Accessibility

Accessibility is a first-class acceptance criterion.

Minimum expectations:

- WCAG AA text contrast;
- keyboard operation;
- visible focus;
- semantic headings;
- useful accessible names;
- sufficient touch targets;
- reduced-motion support;
- no colour-only critical states;
- fatigue-friendly workout controls;
- destructive actions visually distinct.

An element existing in the DOM does not prove accessibility.

## 10. Visual acceptance

For visible UI acceptance, an element must be:

- visible;
- readable;
- reachable;
- understandable;
- in the correct visual state;
- backed by the correct underlying data.

Hidden DOM elements must not satisfy visual acceptance criteria.

Every substantial UI change should be reviewed on:

- compact phone;
- large phone;
- tablet;
- desktop.

Use deterministic review fixtures. Never use production personal data for review captures.

## 11. Security and privacy

Do not expose:

- credentials;
- tokens;
- Home Assistant ingress secrets/session identifiers;
- internal person IDs;
- unnecessary UUIDs;
- raw integration endpoints;
- debug/admin internals.

Shareable review artifacts must be sanitised. Privacy regressions are release blockers.

## 12. Multi-agent organisation

Substantial programmes should use specialised lanes. No agent should treat itself as the sole authority across product, architecture, implementation, QA and release.

### ROLE: Programme / Delivery Lead

Responsibilities:

- reconcile current repository state;
- maintain programme ledger;
- sequence workstreams;
- manage dependencies;
- prevent duplicate work;
- coordinate releases;
- ensure Definition of Done is met.

Must not self-approve architecture changes or bypass failed gates to maintain schedule.

### ROLE: Product / UX Lead

Responsibilities:

- user journeys;
- information architecture;
- interaction hierarchy;
- responsive behaviour;
- acceptance scenarios;
- design-direction reconciliation.

Must not redefine domain authority.

### ROLE: Principal Architect

Responsibilities:

- domain boundaries;
- revision model;
- event contracts;
- integration boundaries;
- architectural review;
- ADR/design-decision review.

Architecture review is required for changes affecting authority, identity, persistence, history, recommendation semantics, integrations or schemas.

### ROLE: Domain Engineer

Responsibilities:

- workout lifecycle;
- programme logic;
- progression rules;
- evidence semantics;
- history/revision behaviour.

Must use TDD and must not allow presentation needs to mutate historical truth.

### ROLE: Frontend Engineer

Responsibilities:

- templates/components;
- responsive layout;
- interactions;
- visual states;
- client-side behaviour;
- UI performance.

Must use shared primitives where appropriate, preserve semantic HTML and consume domain contracts rather than reimplementing authority in presentation code.

### ROLE: Design-System Engineer

Responsibilities:

- tokens;
- spacing;
- typography;
- shared card/button/input primitives;
- responsive primitives;
- dark-mode foundation;
- visual state language.

Must minimise stylistic drift.

### ROLE: Data / Analytics Engineer

Responsibilities:

- read models;
- progress metrics;
- charts;
- PR/e1RM calculations;
- muscle-exposure analytics;
- consistency data.

Must distinguish measured fact, derived metric and recommendation. Derived metrics require deterministic tests.

### ROLE: Accessibility Engineer

Responsibilities:

- semantic review;
- contrast;
- keyboard navigation;
- focus order;
- touch targets;
- screen-reader behaviour;
- reduced motion.

May block release on material accessibility failures.

### ROLE: QA / SDET

Responsibilities:

- risk-based test strategy;
- integration/browser/regression coverage;
- failure cases;
- state transitions;
- person isolation;
- idempotency/stale-write coverage.

Must independently test the implementation rather than trust the implementation author's test list.

### ROLE: Visual QA Engineer

Responsibilities:

- deterministic review pack;
- responsive screenshots;
- hierarchy/spacing/typography review;
- clipping/overflow review;
- real visibility;
- empty/populated states.

Must not count hidden DOM as visible success.

### ROLE: Security / Privacy Engineer

Responsibilities:

- secret leakage;
- ingress sanitisation;
- identity boundaries;
- exported-artifact safety;
- endpoint exposure;
- access-control regression review.

Identity/credential/privacy failures block release.

### ROLE: Home Assistant Integration Engineer

Responsibilities:

- Supervisor Ingress;
- add-on runtime;
- panel integration;
- HA dashboard surfaces;
- notifications;
- restart/reload resilience.

Must not turn generic Home Assistant activity into authoritative workout evidence.

### ROLE: Release / DevOps Engineer

Responsibilities:

- CI;
- build;
- multi-arch image;
- version consistency;
- release workflow;
- artifact retention;
- production-image verification;
- rollback readiness.

Must independently confirm main/release state.

### ROLE: Independent Reviewer

Responsibilities:

- review without assuming the author's conclusions;
- challenge scope creep;
- verify acceptance criteria;
- identify hidden coupling;
- identify missing tests.

Implementation agents must not be the sole reviewers of their own work.

## 13. Workstream isolation

Each workstream must have:

- clear objective;
- allowed mutation scope where practical;
- dependencies;
- acceptance criteria;
- explicit non-goals;
- test strategy;
- review owner.

Avoid concurrent modification of the same files by unrelated agents. When parallelisation is unsafe, serialise the work.

## 14. Branch / PR discipline

Prefer:

`<type>/<release>-<workstream>`

Examples:

- `fix/0140-review-pack-visibility`
- `feat/0200-today-dashboard`
- `feat/0200-workout-complete`
- `feat/0200-progress-strength`

Every PR must include:

- objective;
- release/workstream;
- scope and non-scope;
- architecture impact;
- data/domain impact;
- tests;
- visual evidence for UI changes;
- accessibility review;
- security/privacy review where relevant;
- migration notes;
- rollback considerations.

Keep PRs small enough for meaningful review.

## 15. TDD expectations

Use RED → GREEN → REFACTOR for domain and behavioural logic.

UI work should begin with observable acceptance states where practical.

Permanent regression categories include, as relevant:

- identity isolation;
- workout lifecycle;
- revision semantics;
- stale writes;
- duplicate completion;
- equipment validity;
- progress calculations;
- responsive navigation;
- review capture;
- visibility correctness;
- ingress safety.

## 16. Programme ledger

The UI evolution programme ledger is maintained at:

`docs/programme/ui-evolution/PROGRAMME_LEDGER.md`

Chat is not the programme ledger.

## 17. Architecture decisions

Material architectural decisions require a committed ADR or equivalent approved design decision.

Examples:

- new persistence model;
- new external integration;
- progression authority change;
- authentication/identity change;
- new frontend framework;
- major schema design;
- event-contract change.

Do not bury architecture decisions inside code-review comments.

## 18. Definition of Ready

A workstream is ready when:

- objective is clear;
- dependencies are resolved;
- current repository state is reconciled;
- acceptance criteria exist;
- architecture implications are understood;
- mutation scope is known;
- test strategy exists.

## 19. Definition of Done

A workstream is DONE only when all applicable items are satisfied:

- implementation complete;
- tests green;
- independent review complete;
- architecture accepted where applicable;
- accessibility reviewed;
- visual review completed;
- security/privacy reviewed;
- docs updated;
- no unresolved blocking review comments;
- merged to main;
- main CI green;
- release completed if part of a release;
- production artifact verified if applicable.

PR creation is not completion. Merge is not necessarily release completion.

## 20. Release gates

### Gate A — Domain integrity

- person isolation preserved;
- revision semantics preserved;
- evidence semantics preserved;
- no fabricated state.

### Gate B — Automated quality

Required lint, type, unit, integration, contract, e2e, migration and image/build checks are green.

### Gate C — Accessibility

No known material accessibility blocker.

### Gate D — Visual

Required viewport review complete. No material clipping, unreadable content or hidden-critical-control issue.

### Gate E — Security/privacy

No credential/session/identity leakage.

### Gate F — Release

- correct version;
- correct main;
- supported architecture image verification;
- public/production image verification where applicable;
- rollback path understood.

## 21. Failure policy

Never weaken a test merely to make CI green without understanding the failure.

If expected behaviour changes intentionally:

1. document why;
2. update the contract;
3. update tests;
4. obtain appropriate review.

Fail closed around identity, authority, history, privacy and evidence integrity.

## 22. Strategic roadmap

The governed UI-evolution sequence is:

- **0.1.40** — quality foundation;
- **0.2.0** — Today → Workout → Complete → Progress premium journey;
- **0.2.1** — Plan → Library → Exercise Detail → More;
- **0.2.2** — dark workout mode → motion → Home Assistant ambient surfaces;
- **0.3.x** — governed coaching/progression/adaptation.

Do not opportunistically pull future work into earlier releases unless explicitly approved.

## 23. Final principle

Getfit should become visually competitive with leading commercial fitness products without losing the qualities that make its architecture stronger:

- transparent reasoning;
- local-first operation;
- strict person isolation;
- immutable performed evidence;
- clear ownership boundaries;
- deterministic history;
- safe progression;
- explainable coaching.

When forced to choose between visual convenience and evidence integrity:

> evidence integrity wins.
