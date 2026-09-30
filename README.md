# Home Workout Assistant

Home Workout Assistant (HWA), also known as Getfit, is a local-first Home Assistant application for structured home workout planning, recording, and progression.

## Authority boundaries

- **HWA / Getfit** owns programme prescription, workout drafts, performed workout evidence, correction history, progression history, and the effective workout revision.
- **Pep-Site** owns Health analysis, outcomes, and interpretation.
- **Menu-Nutrition** owns food, calories, macros, and nutrition planning.
- **Health Bridge / Withings / Apple activity data** supplies supporting measured Health/activity evidence only.

Generic steps, exercise minutes, calories, Withings workout summaries, or Apple aggregate activity must never be promoted into authoritative HWA Workout Events.

## Approved design and plans

The repository keeps the approved architecture and product direction under `docs/superpowers/`:

- [`HWA Foundation Design`](docs/superpowers/specs/2026-09-30-hwa-foundation-design.md) — approved architecture and authority baseline.
- [`HWA Foundation Implementation Plan`](docs/superpowers/plans/2026-09-30-hwa-foundation-implementation.md) — Foundation RED→GREEN execution order.
- [`Getfit Consolidated Product Design`](docs/superpowers/specs/2026-09-30-getfit-product-design.md) — approved broader gym-app direction including Today/Workout/Progress/Library/Settings, person isolation, four sessions per week, 52-week programme handling, guided media, progression, workout evidence and cross-project boundaries.
- [`Getfit Product Implementation Plan`](docs/superpowers/plans/2026-09-30-getfit-product-implementation.md) — post-Foundation implementation tasks through authoritative Pep `WORKOUT_EVENT_SOURCE`, Home Assistant ingress and whole-product acceptance.
- `docs/superpowers/approved-foundation-baseline.zip` preserves the exact approved Foundation source documents for audit/recovery.

## Foundation development

Requires Python 3.12+ and [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync --dev
uv run ruff check .
uv run mypy src
uv run pytest -q
```

Implementation follows TDD and exact-head CI evidence. LIVE Pep/Home Assistant mutation and Pep Health activation are separate governance actions and are not implied by Getfit development work.
