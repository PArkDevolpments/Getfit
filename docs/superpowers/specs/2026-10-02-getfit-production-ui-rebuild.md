# Getfit production UI rebuild — diagnosis and delivery notes

Date: 2026-10-02

## Production diagnosis

The 0.1.2 production screenshot shows the application content rendering successfully inside Home Assistant Ingress — Kris is resolved, Week 1 Day 1 is visible, the five navigation labels render and the Start action is present — but browser-default typography, links, list bullets and controls are visible across the page.

The frontend source already contained dark-theme CSS and a mounted FastAPI `/static` directory. The failure was delivery, not an absent stylesheet:

- `base.html` requested `/static/app.css` from the browser origin.
- Workout requested `/static/workout.css` and `/static/workout.js` the same way.
- Navigation, Library links and browser-side API requests were root-absolute.
- Home Assistant Supervisor Ingress serves the app below a per-session `/api/hassio_ingress/<token>` prefix, so those root-absolute browser URLs escaped the ingress base.
- The result matched the production screenshot exactly: HTML worked, CSS did not.

The fix is a validated `X-Ingress-Path` presentation helper. Direct development requests retain normal root paths, while Ingress requests generate browser URLs beneath the Supervisor prefix. No identity or backend routing model is changed.

## UI gap analysis

The working backend was materially ahead of the presentation layer. The old UI exposed correct data, but did not express the approved product direction:

- Today was a stack of plain cards and a list rather than a training dashboard.
- Workout rendered every set and cardio field at once instead of a current/next guided player.
- Progress exposed evidence as utilitarian rows instead of completion and exercise cards.
- Library showed canonical exercise IDs and had little visual hierarchy.
- Settings was safe but read like diagnostic configuration.
- Mobile controls met a basic touch floor, but navigation and in-workout actions were not optimised for use while exercising.

## Design authority translated into components

The Workout Schedule Plan and approved boards establish a dark navy / charcoal product, electric blue highlights, large exercise imagery, strong timers, set/rest information, progress bars and a clear next-action hierarchy. The rebuild translates that language into reusable application components rather than reproducing booklet pages.

Shared system:

- deep navy background with layered blue gradients
- translucent raised surfaces with subtle borders
- electric blue primary CTA and progress treatment
- high-contrast white typography with restrained muted copy
- 18–22 px card radii and large touch controls
- sticky five-surface navigation on desktop and bottom navigation on mobile
- responsive two-column desktop/tablet layouts collapsing cleanly on phone

Today:

- Week/day hero with weekly completion ring and Start/Resume CTA
- session-card grid
- compact Health and Nutrition context cards

Workout:

- one guided stage at a time
- large strength/bike/treadmill visual region
- target chips for prescribed work
- actual reps/load/RPE/RIR entry
- current-set highlighting
- workout progress bar
- rest countdown
- cardio countdowns
- next-stage preview
- Previous / Pause / Skip / Next / Stop controls
- spin bike fields limited to duration/cadence/resistance/RPE
- treadmill fields limited to duration/speed/incline/RPE

Progress:

- completion ring and KPI cards
- per-exercise latest evidence cards
- completed-session timeline
- no internal event IDs in the visible product

Library:

- visual exercise cards
- body-area and movement-family context
- technique cues
- local-media slot with safe fallback
- approved external video only when present
- person-scoped recent exercise history on detail pages

Settings:

- signed-in identity
- installation equipment cards
- treadmill maximum incline capability
- explicit spin-bike no-incline capability
- calibration status
- Pep Health and Menu-Nutrition connection status
- no connection endpoints, tokens or cross-system IDs

## Regression contract

The rebuild keeps backend authority unchanged. Tests now cover:

- validated Supervisor ingress prefix generation
- rendered CSS/navigation/API URLs under `X-Ingress-Path`
- direct `/static/app.css` mounting
- responsive design tokens and navigation contract
- guided workout controls and timers
- no visible implementation exercise IDs in Library detail text
- safe Settings cards
- the existing identity, draft, restart/resume, history, completion and Pep export suites

The release remains gated by exact-head CI, container build, production image publication and Home Assistant post-update smoke verification.
