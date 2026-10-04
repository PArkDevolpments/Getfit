# Getfit Mobile Design Authority v2

**Status:** Locked for implementation  
**Date:** 2026-10-04  
**Primary target:** Home Assistant on iPhone, measured Getfit viewport approximately 440 × 820 CSS px before 0.1.27 shell changes.

## Product intent

Getfit should feel like a finished consumer fitness app rather than a responsive administration dashboard. The visual language is shared with the approved Menu-Nutrition direction without copying food-specific layouts.

The interface is training-first: the user should understand what to do now, record it quickly, and continue without unnecessary scrolling or data-entry friction.

## Locked product navigation

The persistent mobile navigation contains exactly five primary destinations:

1. Today
2. Plan
3. Workout
4. Progress
5. More

Exercise Library is a secondary training surface reachable from Workout/More and technique links. Diagnostics, equipment and integrations live under More.

## Visual system

- Editorial serif titles paired with a functional system sans-serif.
- Tabular numerals for timers, reps, load and training metrics.
- Muted emerald action/success accent rather than neon green.
- Warm off-white light mode.
- Deep slate/green-black dark mode.
- Photography/local exercise media supports the task but must not displace primary workout controls.
- Minimum practical touch target: 44 × 44 CSS px.
- No decorative metrics or invented progress.

## Today

Today prioritises:
- signed-in person;
- current approved workout;
- one dominant Start/Resume action;
- compact weekly position;
- recent completed workout evidence.

Programme browsing belongs on Plan. Deep progression belongs on Progress.

## Plan

Plan renders only approved programme authority. It must not invent rest days, recovery sessions or future progression.

Current, completed and upcoming approved sessions must be visually distinguishable.

## Strength workout

The active 440 × 820 phone view must keep the primary set workflow immediately usable:

- workout/session context;
- exercise identity;
- compact local technique media;
- prescribed reps/load/tempo/rest;
- actual reps/load controls;
- optional exact RPE/RIR;
- Complete Set above the persistent product navigation.

Reps/load use large steppers. Completing a set enters explicit feedback, then rest. Rest completion never auto-advances a strength set.

Quick feedback semantics remain:
- Too easy → estimated RPE 6 / about 4 RIR
- About right → estimated RPE 8 / about 2 RIR
- Too hard → estimated RPE 10 / 0 RIR
- Pain / Stop → safety interrupt

Manual exact RPE/RIR always overrides estimates.

## Cardio workout

Live cardio screens prioritise timer and equipment-specific coaching variables.

Spin bike:
- time
- cadence / RPM
- resistance
- RPE
- never incline

Treadmill:
- time
- speed
- incline
- RPE
- incline capped by installation capability (currently 20%)

Actual RPE uses 44px+ touch controls. Decorative cardio imagery is hidden during the active phone workout.

## Progress

Progress is built only from completed Getfit workout evidence.

Do not display:
- invented calorie burn;
- arbitrary ratings;
- fabricated trend lines;
- guessed achievements;
- unsupported future progression.

Empty states must remain explicit when evidence does not exist.

## Home Assistant mobile shell

Getfit opts into Home Assistant app-frame property updates and manages safe areas itself on mobile.

On narrow screens it requests Home Assistant kiosk presentation so the training surface can use the available phone canvas without a duplicate app toolbar. Getfit receives resolved Home Assistant safe-area insets and keeps interactive controls inside them while allowing the visual canvas/navigation background to reach the device edges.

The shell must gracefully fall back if the parent Home Assistant version ignores these messages.

## Validation

Every release implementing this authority must retain:
- responsive automated review;
- actual-device Auto-review this device flow;
- horizontal overflow checks;
- 44px touch-target checks;
- primary-action viewport visibility;
- bottom-navigation viewport geometry checks;
- live cardio target visibility checks.

The real iPhone/Home Assistant device review remains the final visual authority over simulated desktop screenshots.
