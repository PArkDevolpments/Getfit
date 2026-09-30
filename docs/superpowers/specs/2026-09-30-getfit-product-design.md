# Getfit / Home Workout Assistant — Consolidated Product Design v1.0

**Status:** Approved product direction consolidated from prior Getfit/Home Workout Assistant decisions  
**Repository:** `ktgregson93-collab/Getfit`  
**Relationship to Foundation:** Extends, but does not replace, `2026-09-30-hwa-foundation-design.md`  

## Product purpose

Getfit (Home Workout Assistant / HWA) is the local-first gym and home-workout application for planning, guiding, recording, correcting, and progressing structured workouts.

The app is the authoritative producer of structured workout evidence. It owns programme/week/day prescription, exercises, sets/repetitions or timed work, performed loads, RPE/RIR, treadmill performance, spin-bike performance, completion state, correction history, progression history, and the effective workout record.

Authority boundaries remain strict:

- **Getfit/HWA** owns structured workout prescription and performed workout evidence.
- **Pep-Site Health** consumes workout evidence and owns Health analysis/outcome interpretation.
- **Menu-Nutrition** owns nutrition, calorie, macro and meal-planning authority.
- **Health Bridge / Withings / Apple / Home Assistant activity sensors** are supporting measured context only.
- Steps, exercise minutes, active calories, a Withings “last workout”, or an Apple aggregate workout must never be promoted into an authoritative Getfit workout event.

## People and identity

The product supports separate person-scoped experiences and history. The currently agreed identities are Kris and Kirsty, resolved from trusted Home Assistant identity rather than from a display-name selector.

- Kris maps to Pep `person_a`, Health `kris`, Menu `person_1`.
- Kirsty maps to Pep `person_b`, Health `kirsty`, Menu `person_2`.
- Production identity is trusted only through Home Assistant Supervisor Ingress plus explicit stable-user mapping.
- Missing, ambiguous, spoofed, or cross-person identity fails closed.
- Targets, calibration, workout history, progression and draft sessions are person scoped. There is no fallback from Kirsty to Kris or vice versa.

## Training scope

The agreed product direction is a 12-month / 52-week programme experience built around four structured sessions per week.

Available home equipment includes:

- treadmill with incline support;
- spin bike with no incline concept;
- adjustable dumbbells / weights.

The programme must use explicit targets where the approved prescription provides them, including treadmill speed/incline and strength loads. Spin-bike work uses duration, cadence/resistance and effort; it must never expose or store bike incline.

Starting loads and later progression are individual. They are calibrated from actual performed evidence and user feedback rather than derived mechanically from sex or bodyweight.

The Foundation Week 1 programme remains the first production-shaped seed. Day 4 retains the approved conservative structure: five bike rounds of 30 seconds hard / 90 seconds recovery, followed by controlled steady treadmill work using calibration targets. Full 52-week programme content is added only from approved programme material; the implementation must not invent missing prescriptions.

## Primary product experience

The approved navigation direction is deliberately simple and usable during training:

1. **Today** — the current programme position, next workout, readiness/context summary where available, and a clear start/resume action.
2. **Workout** — the guided in-session experience, current exercise/set, target, actual entry, rest/work timing, RPE/RIR capture, and completion controls.
3. **Progress** — workout adherence, performed progression and training history based on Getfit evidence; Health meaning remains a Pep responsibility.
4. **Library** — programme days/exercises and technique/demo material.
5. **Settings** — person-safe configuration, equipment/calibration and integration state without exposing cross-person data.

The interface should avoid a cramped “wall of numbers”. During a live workout the next action, target and actual input are primary; secondary metrics are subordinate.

## Exercise guidance and media

Exercises should be understandable without leaving the workout flow.

- Support local/animated exercise demonstrations as the primary in-app guidance direction.
- Allow approved example video links/embeds, including YouTube, as optional supporting technique material.
- Media is guidance only and must not be required to preserve or complete a workout record.
- A missing media asset must not block workout execution or evidence capture.

## Workout lifecycle

Programme prescription and performed reality are separate.

1. A planned workout defines the intended exercises and targets.
2. Starting a workout creates a mutable person-scoped draft.
3. Every meaningful in-session edit autosaves to the draft.
4. Interrupted sessions are resumable.
5. Completion atomically creates immutable Revision 1 of the performed workout.
6. Later corrections create immutable later revisions with explicit supersession.
7. Autosaves never create historical workout revisions.
8. The logical `event_id` remains stable across corrections.
9. Only the effective revision is exported to downstream consumers.

## Canonical workout evidence

The canonical model must support, at minimum:

- stable `event_id` and immutable revision identity;
- person identity and provenance;
- programme/week/day/workout identity;
- start/end instants persisted in UTC and presented in `Europe/London`;
- duration as unambiguous `duration_seconds`;
- exercise order and exercise identity;
- repetition and timed sets;
- laterality (`BILATERAL`, `LEFT`, `RIGHT`, `EACH_SIDE`);
- load amount/unit and explicit load mode (`EACH_HAND`, `SINGLE_IMPLEMENT`, `TOTAL_EXTERNAL`, `BODYWEIGHT`, `ASSISTED`, `NONE`);
- RPE 1.0–10.0 and RIR 0–5 where captured;
- treadmill duration/speed/incline/RPE;
- spin-bike duration/cadence/resistance/RPE, with incline structurally invalid;
- completion status and correction/supersession metadata;
- optional physiological evidence only when genuinely measured.

Missing optional heart-rate, training-load, cadence or similar evidence remains unavailable rather than estimated.

## Progression

Progression is driven by performed Getfit evidence, not by assumed completion of the prescription.

The product must preserve enough evidence to compare repeated sessions/exercises and support later progression decisions. Progression logic must remain person scoped and explain what evidence caused a target to change. It must not silently rewrite historical prescriptions or completed records.

Where a target cannot yet be safely determined from approved programme rules and actual evidence, the app keeps the existing approved target or requests calibration rather than fabricating a new one.

## Cross-project integration

### Pep-Site Health

Getfit is the authoritative producer for Pep `WORKOUT_EVENT_SOURCE`.

The export boundary is read-only from Pep's perspective and must be:

- person scoped;
- provenance preserving;
- revision/effective-record aware;
- deterministic and idempotent;
- fail closed when Getfit is unavailable or identity cannot be proved.

Pep must never reconstruct structured workouts from Health Bridge/Withings/Apple aggregate activity to cover a Getfit outage.

### Pep Health context

Getfit may read approved person-scoped Pep Health context for training context, but it does not gain mutation or Health-interpretation authority.

### Menu-Nutrition

Getfit may read approved person-scoped Menu-Nutrition context. It does not own calorie/macro targets and cannot mutate Menu data.

## Home Assistant deployment direction

The application is local-first and intended to run behind Home Assistant Supervisor Ingress. Production identity/trust behavior must remain distinct from development/test authentication. Direct client-supplied identity headers are not sufficient production authentication.

## Resilience and usability

A workout must remain usable through ordinary interruptions:

- refresh/reopen resumes the same active draft for the same person;
- duplicate completion requests are idempotent;
- concurrent/stale writes cannot overwrite newer evidence silently;
- a failed downstream integration does not destroy a completed workout;
- a missing optional sensor or media source does not prevent exercise logging;
- cross-person data never appears as a fallback.

## Quality model

Implementation remains TDD-first and permanently regression tested. A functional-looking screen is not completion.

Permanent coverage must include identity isolation, UTC/DST handling, migrations, schema validation, load/timed/unilateral semantics, equipment rules, draft recovery, concurrency, idempotent completion, immutable corrections, effective read model, Pep projection, read-only Pep/Menu boundaries, browser workflow, responsive/touch usability, and end-to-end acceptance.

## Explicit non-goals / protected boundaries

- No LIVE Pep or Home Assistant data mutation from design work.
- No automatic Pep Health activation.
- No substitution of aggregate activity for structured workouts.
- No guessed Home Assistant user IDs.
- No cross-person fallback.
- No spin-bike incline.
- No fabricated physiological evidence.
- No automatic nutrition authority transfer to Getfit.
- No silent rewriting of completed workout history.
- No invention of unapproved 52-week prescriptions merely to fill the calendar.

> Getfit records what training was prescribed and what actually happened. Pep analyses its Health significance. Menu owns nutrition. Health Bridge/Withings/Apple provide supporting measurements only.
