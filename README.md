# Home Workout Assistant

Home Workout Assistant (HWA), also known as Getfit, is a local-first Home Assistant application for structured home workout planning, recording, and progression.

## Authority boundaries

- **HWA / Getfit** owns programme prescription, workout drafts, performed workout evidence, correction history, progression history, and the effective workout revision.
- **Pep-Site** owns Health analysis, outcomes, and interpretation.
- **Menu-Nutrition** owns food, calories, macros, and nutrition planning.
- **Health Bridge / Withings / Apple activity data** supplies supporting measured Health/activity evidence only.

Generic steps, exercise minutes, calories, Withings workout summaries, or Apple aggregate activity must never be promoted into authoritative HWA Workout Events.

## Optional Pep Health context

Pep Health context is read-only, presentation-only and **off by default**:
`pep_health_enabled: false`. Pep's Health-authority flag is separately governed.
When disabled, Getfit loads no signing key and makes no Health service request.
Unavailable Health never blocks workout planning, drafts, completion or history.
An enabled reader fails closed on invalid configuration, identity, assertions,
Pep denials, protocol errors or timeouts; it retains no previous successful
projection and performs no local Health calculation or fallback.

Getfit uses the trusted Home Assistant Ingress subject, one active Ed25519
private key and `kid`, and an assertion-only HA service call. Pep makes the final
subject-to-person mapping. The private key crosses into Python through an
owner-readable file, never an inline environment value or browser response.
The add-on grants the required `homeassistant_api: true` permission.

See [add-on operations](getfit/DOCS.md) for unavailable states, configuration,
Pep public-key overlap, rotation, revocation and rollback. H6 local verification
does not authorize LIVE keys, mappings, deployment or activation. Independent
whole-branch architecture/security/privacy review accepted `29dfdd6` on
2026-10-12; verification and independent review of subsequent changes remain
separate gates. Exact current-image identity is still blocked, and representative
staging, remote exact-head CI and release/production-artifact gates remain open;
see [H6 evidence](docs/superpowers/evidence/2026-10-08-getfit-h6-contract-evidence.md)
and the [unexecuted staging L1 runbook](docs/superpowers/evidence/2026-10-12-getfit-h6-staging-l1-acceptance.md).

## Approved design and plans

The repository keeps the approved architecture and product direction under `docs/superpowers/`:

- [`HWA Foundation Design`](docs/superpowers/specs/2026-09-30-hwa-foundation-design.md) — approved architecture and authority baseline.
- [`HWA Foundation Implementation Plan`](docs/superpowers/plans/2026-09-30-hwa-foundation-implementation.md) — Foundation RED→GREEN execution order.
- [`Getfit Consolidated Product Design`](docs/superpowers/specs/2026-09-30-getfit-product-design.md) — approved broader gym-app direction including Today/Workout/Progress/Library/Settings, person isolation, four sessions per week, 52-week programme handling, guided media, progression, workout evidence and cross-project boundaries.
- [`Getfit Product Implementation Plan`](docs/superpowers/plans/2026-09-30-getfit-product-implementation.md) — post-Foundation implementation tasks through authoritative Pep `WORKOUT_EVENT_SOURCE`, Home Assistant ingress and whole-product acceptance.
- `docs/superpowers/approved-foundation-baseline.zip` preserves the exact approved Foundation source documents for audit/recovery.

## Active UI/UX evolution programme

The governed premium-product evolution is tracked under `docs/programme/ui-evolution/`.

Start with:

- [`AGENTS.md`](AGENTS.md) — repository-wide engineering operating contract for human and agentic contributors.
- [UI/UX Evolution Programme](docs/programme/ui-evolution/README.md) — programme index and release sequence.
- [Programme Ledger](docs/programme/ui-evolution/PROGRAMME_LEDGER.md) — authoritative workstream status.
- [Workstream Catalogue](docs/programme/ui-evolution/WORKSTREAM_CATALOGUE.md) — stable `GF-xxxx-xx` workstream IDs.
- [Acceptance and Release Gates](docs/programme/ui-evolution/ACCEPTANCE_AND_RELEASE_GATES.md) — Definition of Done and release controls.

## Foundation development

Requires Python 3.12+ and [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync --dev
uv run ruff check .
uv run mypy src
uv run pytest -q
```

Implementation follows TDD and exact-head CI evidence. LIVE Pep/Home Assistant mutation and Pep Health activation are separate governance actions and are not implied by Getfit development work.
