# Home Workout Assistant Foundation Implementation Plan v1.1

> **Status:** APPROVED IMPLEMENTATION BASELINE
> **Supersedes:** Foundation Implementation Plan v1.0

This repository copy is the readable execution index for the approved v1.1 plan. The exact user-approved source documents are preserved in `docs/superpowers/approved-foundation-baseline.zip` for audit/recovery.

## Global requirements

- HWA is authoritative for structured workout evidence.
- Pep-Site remains authoritative for Health analysis.
- Menu-Nutrition remains authoritative for nutrition.
- Health Bridge remains supporting measurement evidence only.
- Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, SQLite/WAL.
- Persist instants as UTC; present in `Europe/London`; reject naive timestamps.
- Trusted production identity requires Home Assistant Supervisor Ingress + `X-Remote-User-Id` + explicit mapping.
- Direct spoofed identity headers fail closed.
- Kris maps to Pep `person_a`, Health `kris`, Menu `person_1`; Kirsty maps to `person_b`, `kirsty`, `person_2`.
- Display names are never persistence or ownership keys.
- Programme prescription and performed evidence are separate.
- Active workout drafts are mutable/resumable; completed/corrected workout revisions are immutable.
- RPE 1.0–10.0; RIR 0–5.
- Load modes: `EACH_HAND`, `SINGLE_IMPLEMENT`, `TOTAL_EXTERNAL`, `BODYWEIGHT`, `ASSISTED`, `NONE`.
- Strength targets support `REPS` and `DURATION`; laterality supports `BILATERAL`, `LEFT`, `RIGHT`, `EACH_SIDE`.
- Treadmill supports incline; spin bike structurally rejects incline.
- Missing HR/training-load evidence remains unavailable rather than estimated.
- HWA canonical storage uses `duration_seconds` and structured `effort.session_rpe`.
- Pep `duration`/`effort` translation stays gated until real provider binding.
- No Pep source changes or LIVE activation in Foundation.

## Implementation order

1. Repository foundation and permanent CI.
2. UTC/timezone boundary.
3. SQLite/WAL and migration infrastructure.
4. Trusted Home Assistant identity.
5. Canonical programme/workout schemas.
6. Final Week 1 prescription lock and seed.
7. Workout persistence including resumable drafts.
8. Idempotency and corrections.
9. Person-scoped API.
10. Pep workout projection.
11. Pep Health reader.
12. Menu-Nutrition reader.
13. Foundation browser workflow.
14. Full Foundation acceptance.

Every task follows RED → observed failure → minimal implementation → focused GREEN → regression suite → commit/review gate.

## Week 1 lock

Before Task 6, reconcile the complete Day 1–4 prescription. Day 4 must use the approved conservative structure: 5 bike rounds of 30s hard / 90s recovery, followed by controlled steady treadmill work using calibration targets. No second treadmill interval programme; no spin-bike incline; no Kirsty fallback to Kris starter loads.

## Foundation quality gate

From a clean checkout:

```text
ruff check .
mypy src
pytest tests/unit -q
pytest tests/integration -q
pytest tests/contract -q
pytest tests/e2e -q
alembic upgrade head
```

Then run branch CI. Foundation is not complete until all required suites are freshly green, person isolation is permanent QA, drafts survive interruptions, autosaves are not revisions, completion creates Revision 1, corrections create later immutable revisions, and external authority boundaries remain intact.
