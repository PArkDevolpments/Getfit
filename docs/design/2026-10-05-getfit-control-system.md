# Getfit interaction controls — v1

Status: authoritative from 0.1.34.

This is the shared interaction language for Getfit. Do not style primary product buttons independently unless a state genuinely needs a new semantic control.

## Core hierarchy

- **Primary** — one dominant action for the current state. Examples: Start Workout, Complete Set, Start next set, Complete workout.
- **Secondary** — useful but subordinate. Examples: Add rest, Pause, Explore library.
- **Ghost** — navigation, dismissal or low-emphasis actions. Examples: Back, Skip, Reset.
- **Danger** — stop/remove/safety actions. Use restrained red; do not make an entire normal screen red.
- **Icon** — compact single-icon control. Minimum 44×44px and always needs an accessible name.

## Touch and geometry

- Standard minimum height: 48px.
- Primary action minimum height: 54px.
- Icon control: minimum 44×44px.
- Standard radius: 14px.
- Primary radius: 16px.
- Buttons use the shared `controls.css` tokens and are loaded after page-specific styles.

## State rules

Every interactive control must have:
- default
- pressed
- focus-visible
- disabled
- loading where network latency is possible

Never use opacity alone to communicate selected/completed/dangerous meaning.

## Icons

Use simple inline SVG with `currentColor`, rounded line caps and no raster button artwork. This keeps controls crisp at every device density and lets light/dark themes share the same assets.

## Workout

Strength:
- Complete Set is the single primary action.
- Easy / Moderate / Hard / Max are segmented state choices, not four competing CTAs.
- Report pain / stop exercise is a danger control.
- Exact RPE/RIR stays secondary.

Rest:
- Start next set = primary.
- Add rest = secondary.
- End/stop = danger or low-emphasis danger depending on state.

Cardio:
- Start/Pause = primary.
- Reset = icon/ghost.
- Complete Segment remains clear but must not compete with Start/Pause while the timer is active.

## Accessibility

- No interactive target below 44×44px.
- Focus-visible ring must be obvious in both colour schemes.
- Text and icon contrast must remain readable in light and dark modes.
- Respect `prefers-reduced-motion`.
- Never use browser zoom or transform scaling to make controls fit.
