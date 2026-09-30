# Home Workout Assistant

Home Workout Assistant (HWA) is a local-first Home Assistant application for structured home workout planning, recording, and progression.

## Authority boundaries

- **HWA** owns programme prescription, workout drafts, performed workout evidence, correction history, and the effective workout revision.
- **Pep-Site** owns Health analysis, outcomes, and interpretation.
- **Menu-Nutrition** owns food, calories, macros, and nutrition planning.
- **Health Bridge** supplies supporting measured Health/activity evidence only.

Generic steps or exercise minutes must never be promoted into authoritative HWA Workout Events.

## Foundation development

Requires Python 3.12+ and [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync --dev
uv run ruff check .
uv run mypy src
uv run pytest -q
```

The approved design and implementation plan live under `docs/superpowers/`.
