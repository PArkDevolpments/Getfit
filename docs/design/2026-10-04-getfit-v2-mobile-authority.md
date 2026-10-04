# Getfit v2 mobile visual authority — 2026-10-04

Status: **LOCKED WITH MINOR CHANGES (9/10)**

This document is the repository-side visual authority for Getfit mobile work after 0.1.29.

## Source hierarchy

1. **Getfit Fitness App UI Design Board.png** / **image(20261004-103049).png** — latest approved v2 board.
2. Latest real iPhone / Home Assistant device-review screenshots.
3. Current implementation.
4. Older Home Workout Assistant Design Board / UX Board — historical concept material only. Do not use these as the visual target.

## Locked product language

- Navigation: **Today · Plan · Workout · Progress · More**
- Mobile-first reference viewport: **440 × 820 usable app viewport**
- Minimum interactive target: **44 × 44 px**
- Typography: editorial serif for important titles; functional sans for controls, labels and metrics; tabular numerals for workout data.
- Light mode: warm off-white/cream canvas, dark ink text, muted neutral secondary text, emerald actions.
- Dark mode: deep green-black/slate surfaces, restrained emerald highlights, no neon/glow-heavy styling.
- Imagery is deliberate and useful; avoid decorative bloat.
- No invented/fake data to make a mockup look populated.
- Equipment-specific cardio remains truthful:
  - spin bike = cadence + resistance + RPE
  - treadmill = speed + incline + RPE, incline capped at 20%

## Active strength authority

The 440 × 820 strength screen is a single coaching surface:

1. Compact session context and progress.
2. Large approved movement image.
3. Technique pill overlaid on the image.
4. Serif exercise title.
5. One-line prescription summary: sets · reps · load · tempo.
6. Current set label.
7. Dual reps/load steppers.
8. Four quick effort choices: **Easy · Moderate · Hard · Max**.
9. Full-width **Complete Set** action inside the exercise surface and above product navigation.

Do not reintroduce:
- detached/floating CTA with large dead space,
- repeated set labels,
- three boxed prescription tiles on phone,
- form-heavy styling,
- low-contrast labels.

Exact RPE/RIR and Pain/Stop remain available as secondary detail/safety controls without dominating the primary flow.

## Active cardio authority

Bike and treadmill are separate equipment-specific screens.

The live mobile hierarchy is:

1. Compact session/stage context and progress.
2. Equipment title.
3. Large circular timer with restrained emerald progress ring.
4. Two primary equipment metrics:
   - Bike: cadence + resistance
   - Treadmill: speed + incline
5. Actual RPE stepper.
6. Primary timer control (Start/Pause) and compact reset.
7. Secondary complete-segment action.

Do not replace the circular live timer with a dashboard-style rectangular timer card.

Interval HARD / RECOVERY states use the same core layout with compact state/round context.

## Other surfaces

- Today: photo-led next-workout card, weekly state, readiness, recent workouts.
- Plan: compact week list with useful imagery and muted rest/recovery days.
- Progress: data-led, concise, high-contrast; avoid essay-style explanatory copy dominating the viewport.
- Library: search + filters + exercise imagery/list/grid with clear text.
- More: profile and concise settings rows first; diagnostics and advanced details remain secondary.

## Home Assistant

Safe-area ownership must remain dynamic and Home Assistant-aware. The product must continue to work in the normal ingress path while the full-canvas companion remains an optional host improvement.

## Change rule

Future UI work must compare against this authority and the latest real-device pack before implementation. Older concept boards may explain product history but must not supersede v2.
