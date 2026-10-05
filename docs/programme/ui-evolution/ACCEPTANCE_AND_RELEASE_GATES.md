# Getfit UI/UX Evolution Acceptance and Release Gates

## Acceptance principle

A feature is not complete because code exists or an element appears in the DOM.

For UI acceptance, the intended user must be able to:

- see it;
- read it;
- reach it;
- understand it;
- interact with it where applicable;
- observe the correct state;
- receive data from the correct authority/provenance.

## Evidence types

Use the strongest applicable evidence:

1. domain/unit tests;
2. integration/contract tests;
3. browser/e2e tests;
4. deterministic review-state captures;
5. accessibility checks;
6. independent visual review;
7. privacy/security review;
8. production release verification.

No single evidence type replaces all others.

## Required viewport review

Material UI changes should be reviewed at:

- compact phone;
- large phone;
- tablet;
- desktop.

Review should include, where relevant:

- empty state;
- populated state;
- active state;
- completed state;
- failure/degraded state;
- long text;
- touch controls;
- keyboard focus.

## Release Gate A — Domain integrity

- trusted identity still fails closed;
- no cross-person leakage;
- workout lifecycle preserved;
- immutable revision semantics preserved;
- no fabricated evidence;
- equipment semantics valid;
- Getfit/Pep/Menu authority unchanged unless separately approved.

## Release Gate B — Automated quality

All required repository checks are green, including relevant:

- Ruff;
- mypy;
- unit;
- integration;
- contract;
- e2e;
- migration;
- packaging/container;
- release-version contracts.

A failing test is investigated, not weakened merely to obtain green CI.

## Release Gate C — Accessibility

No known material blocker.

Review:

- contrast;
- keyboard/focus;
- accessible names;
- semantic structure;
- touch target size;
- reduced-motion behaviour;
- colour-independent state communication.

## Release Gate D — Visual quality

Required viewport evidence is trustworthy and reviewed.

No material:

- clipping;
- overflow;
- unreadable text;
- hidden critical control;
- accidental disabled-looking CTA;
- broken tablet/desktop composition;
- stale or misleading state.

## Release Gate E — Security/privacy

No leakage of:

- credentials;
- tokens;
- HA ingress/session identifiers;
- internal person IDs;
- unnecessary UUIDs;
- raw internal endpoints;
- debug/admin material.

Review artifacts must be safe to share.

## Release Gate F — Release integrity

Before declaring a release complete:

- current main is reconciled;
- version fields are aligned;
- release workflow succeeded;
- supported architecture images published where applicable;
- production/public image verification passed where applicable;
- rollback path is understood;
- programme ledger updated.

## Independent review rule

The implementation author/agent must not be the only source of approval.

At minimum substantial work should receive independent perspectives for:

- architecture/domain where relevant;
- QA;
- accessibility/visual;
- security/privacy where relevant;
- release verification.

## Workstream Definition of Done

A workstream is DONE only when all applicable items are true:

- implementation complete;
- focused tests green;
- regression suite green;
- independent review complete;
- accessibility reviewed;
- visual evidence reviewed;
- privacy/security reviewed;
- documentation updated;
- no unresolved blocking threads;
- merged to main;
- main CI green;
- programme ledger updated;
- release gate complete if the workstream belongs to a release.
