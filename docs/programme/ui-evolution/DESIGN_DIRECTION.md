# Getfit UI Design Direction

## Status

Approved direction for the UI/UX evolution programme. This document describes the intended product language; individual mockups are directional rather than pixel-perfect contracts.

## Visual language

Preserve and evolve the current Getfit identity:

- warm cream/off-white surfaces;
- dark high-contrast ink;
- restrained Getfit green;
- purposeful rounded cards;
- fewer unnecessary nested panels;
- subtle shadows;
- meaningful exercise imagery;
- stronger information hierarchy;
- premium native-app feel while remaining web/Home Assistant based.

Avoid:

- gratuitous gradients;
- constant animation;
- excessive glass effects;
- gamification clutter;
- dashboard walls of numbers;
- low-contrast decorative text;
- oversized empty cards on desktop.

## Today

Target hierarchy:

1. greeting and restrained readiness context;
2. dominant next-workout hero;
3. Start/Resume action;
4. next target and reason;
5. weekly progress;
6. compact weekly timeline;
7. last workout summary.

Example content:

- `Good evening, Kris`
- `Pep readiness: Normal`
- `Upper Body + Bike`
- `Week 1 · Day 1 · ~43 min`
- `Resume workout`
- `Floor Press · 6.5 kg each × 8–10`
- `↑ 0.5 kg from last successful session`
- `3 of 4 workouts this week`

Readiness is contextual. It must not silently mutate training prescription.

## Live workout

Preserve the existing strong sequence:

`exercise → target → actual → effort → Complete Set → feedback → rest → next`

Enhance it with:

- visible previous comparable performance;
- compact explainable coach recommendation;
- genuine mobile secondary controls;
- technique/media access;
- strong primary completion CTA.

Example:

**Last time**  
`6 kg × 10, 10 · RPE 7`

**Coach**  
`Increase 0.5 kg — both sets reached the top of the range last time.`

Mobile must visibly expose Previous, Pause, Skip and Stop without competing with Complete Set.

## Workout Complete

Completion becomes a first-class reward/summary surface.

Potential evidence-backed items:

- duration;
- exercises completed;
- working sets;
- average RPE;
- comparable-session volume change;
- genuine PR;
- next workout;
- coach adjustments.

The experience should feel rewarding but restrained.

## Progress

Top-level modes:

- Strength;
- Training;
- Muscles;
- Consistency.

Strength should provide selectable time range and supported metric, useful charting and concise best/current summaries.

Muscle activity is descriptive training exposure only. A highlighted muscle does not mean recovered or ready.

Consistency should centre planned-versus-completed structured sessions.

## Plan

The 52-week programme should feel like a journey through training blocks rather than a wall of 52 buttons.

Current week must clearly distinguish completed, next, upcoming and eventually missed/rescheduled states.

## Library

Prefer denser scan-friendly exercise rows/cards, good search and compact filtering. Keep the local approved exercise catalogue rather than importing a huge external catalogue.

## Exercise Detail

Target information architecture:

- Technique;
- History;
- Progress.

Use canonical exercise identity across all tabs.

## More

Group secondary functions coherently:

- Training;
- Connected;
- Your Data;
- Getfit.

## Dark mode

First-class dark treatment is most valuable during active workout, rest, treadmill, bike and intervals.

## Motion

Motion must explain state change:

- set completion;
- transition to rest;
- progression change;
- PR;
- interval HARD/RECOVERY transition.

Respect reduced-motion preference.

## Responsive design

Explicit targets:

| Class | Approximate width |
|---|---:|
| Compact phone | 390–440 px |
| Large phone | 430–480 px |
| Tablet | 768–1024 px |
| Desktop | 1200 px+ |

Phone is action-first single column.

Tablet and desktop should use meaningful additional columns and information density rather than stretching phone cards.

## Accessibility baseline

- WCAG AA text contrast;
- minimum practical touch targets;
- visible focus;
- semantic headings;
- no critical colour-only states;
- reduced-motion support;
- fatigue-friendly workout controls.
