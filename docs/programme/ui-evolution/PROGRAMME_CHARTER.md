# Getfit UI/UX Evolution Programme Charter

## Objective

Move Getfit from a strong Home Assistant workout application into a premium digital personal trainer while preserving its existing architectural advantages.

The programme should improve the product's ability to answer:

1. What am I doing today?
2. What do I do right now?
3. Why is this my target?
4. Am I improving?

## Product north star

> Calm personal trainer + premium fitness app + transparent coaching.

## Protected architecture

Getfit remains authoritative for:

- programme prescription;
- workout drafts;
- performed workout evidence;
- corrections and effective revision;
- training progression/history;
- training recommendations.

Pep-Site remains authoritative for health/readiness interpretation and outcomes.

Menu-Nutrition remains authoritative for calorie, macro and nutrition planning.

Health Bridge, Withings, Apple activity and Home Assistant aggregate activity remain supporting context only.

## Protected workout lifecycle

`plan → mutable person-scoped draft → autosave/resume → atomic immutable Revision 1 completion → immutable correction/supersession`

The UI programme must not:

- create historical revisions during autosave;
- rewrite completed evidence;
- bypass stable event identity;
- export non-effective revisions as current;
- convert aggregate activity into Getfit workouts;
- weaken duplicate-completion or stale-write protection.

## Identity

Person identity remains trusted Home Assistant identity.

Missing, ambiguous, spoofed or cross-person identity fails closed.

There is never a cross-person fallback.

## Equipment

- treadmill: speed/incline/duration/RPE as supported;
- spin bike: duration/cadence/resistance/RPE, no incline;
- adjustable dumbbells: explicit load amount and load basis.

## Programme shape

- 52 weeks;
- four sessions per week;
- later programme content may only come from approved programme material.

## Delivery model

Treat this as a multi-disciplinary product programme with independent architecture, implementation, QA, accessibility, visual, privacy and release review.

Substantial work must use the role model in `AGENTS.md`.

## Key constraints

- No framework rewrite merely for visual novelty.
- No social-network scope.
- No nutrition duplication.
- No generic AI chatbot as a substitute for explainable training decisions.
- No recovery/readiness score invented by Getfit.
- No huge external exercise catalogue without explicit governance.
- No UI acceptance based on hidden DOM.

## Definition of success

The programme succeeds when Getfit feels like a purpose-built digital personal trainer rather than a generic web dashboard, while its training evidence and authority model remain at least as strong as before.
