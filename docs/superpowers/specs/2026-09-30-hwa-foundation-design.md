# Home Workout Assistant — Foundation Design Specification v1.0

**Status:** Approved design baseline  
**System:** Home Workout Assistant (HWA)  
**Initial milestone:** HWA Foundation

## Purpose and authority

HWA is a separate local-first application responsible for planning, recording, and progressing structured home workouts. It owns workout prescription, in-progress workout drafts, performed workout evidence, workout correction history, and the effective workout record. Pep-Site remains authoritative for Health analysis; Menu-Nutrition remains authoritative for nutrition; Health Bridge supplies supporting measured signals only. Generic steps or exercise minutes are never converted into first-class workouts.

## Foundation scope

Foundation proves: Home Assistant person identity for Kris/Kirsty, versioned SQLite persistence and migrations, a canonical Workout Event v1, immutable corrections and idempotency, a Pep `WORKOUT_EVENT_SOURCE` projection boundary, read-only Pep Health and Menu-Nutrition readers, a production-shaped Week 1 programme seed, and permanent automated QA. Polished UI, media, the full 52-week programme, advanced progression, and wearable integrations are deferred.

## Identity

Stable machine identity is authoritative; display names are presentation only. Kris maps to Pep `person_a`, Health `kris`, and Menu `person_1`. Kirsty maps to Pep `person_b`, Health `kirsty`, and Menu `person_2`. Home Assistant stable user IDs are installation configuration and are never guessed. Every person-scoped read/write fails closed when identity cannot be proven, and cross-person fallback is prohibited.

## Authentication

Production requests are authenticated only through trusted Home Assistant Supervisor Ingress. A valid-looking `X-Remote-User-Id` header on a direct FastAPI request is insufficient. Development/test authentication uses a separate provider and must not weaken production behavior.

## Workout lifecycle and evidence

Programme prescription is separate from reality. A workout starts as mutable, versioned draft state that is autosaved and resumable. Completion atomically creates immutable Revision 1 and marks it effective. Corrections create immutable later revisions with explicit supersession; autosaves never create historical revisions. Logical `event_id` remains stable across corrections.

Strength evidence supports repetition and timed sets, laterality, explicit load units and load modes (`EACH_HAND`, `SINGLE_IMPLEMENT`, `TOTAL_EXTERNAL`, `BODYWEIGHT`, `ASSISTED`, `NONE`), RPE 1–10, and RIR 0–5. Treadmill can carry duration/speed/incline/RPE. Spin bike can carry duration/cadence/resistance/RPE and structurally rejects incline.

Missing optional physiological evidence remains explicitly unavailable rather than estimated.

## Integration boundaries

HWA exposes only effective structured workout evidence to Pep through a dedicated projection adapter. Pep's exact generic `duration` and `effort` projection semantics remain an explicit future binding gate; HWA canonical storage uses unambiguous `duration_seconds` and structured effort internally. HWA reads Pep Health context and Menu-Nutrition context through typed, person-scoped, fail-closed read adapters and never gains mutation authority over those systems.

## Foundation gate

Foundation is accepted only after permanent identity isolation, ingress trust, UTC/DST, migrations, workout schema, load/timed/unilateral semantics, equipment rules, Week 1 seed, draft recovery/concurrency, completion/idempotency/corrections, effective read model, Pep/Menu contracts, browser workflow, and end-to-end acceptance tests are green. Functional-looking screens are not sufficient.

> HWA records what workout actually happened; Pep analyses its Health significance; Menu owns nutrition; Health Bridge supplies supporting measurements.
