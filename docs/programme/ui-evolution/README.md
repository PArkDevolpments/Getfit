# Getfit UI/UX Evolution Programme

**Status:** Programme governance baseline  
**Repository:** `ktgregson93-collab/Getfit`  
**Starting product release:** 0.1.39  
**Operating contract:** [`AGENTS.md`](../../../AGENTS.md)

## Purpose

This directory is the committed control plane for the Getfit UI/UX evolution programme.

The programme target is:

> Calm personal trainer + premium fitness app + transparent coaching.

The work is intentionally split into governed releases so UI polish cannot bypass identity, evidence, revision, privacy or reliability guarantees.

## Read first

1. [Programme Charter](PROGRAMME_CHARTER.md)
2. [Design Direction](DESIGN_DIRECTION.md)
3. [Workstream Catalogue](WORKSTREAM_CATALOGUE.md)
4. [Acceptance and Release Gates](ACCEPTANCE_AND_RELEASE_GATES.md)
5. [Programme Ledger](PROGRAMME_LEDGER.md)

The existing approved architecture and product specifications remain authoritative prerequisites:

- `docs/superpowers/specs/2026-09-30-hwa-foundation-design.md`
- `docs/superpowers/specs/2026-09-30-getfit-product-design.md`
- `docs/superpowers/plans/2026-09-30-getfit-product-implementation.md`

This programme extends those documents. It does not replace them.

## Release sequence

| Release | Purpose |
|---|---|
| 0.1.40 | Quality foundation and trustworthy review evidence |
| 0.2.0 | Today → Workout → Complete → Progress premium experience |
| 0.2.1 | Programme/discovery surfaces: Plan, Library, Exercise Detail, More |
| 0.2.2 | Dark workout mode, motion and Home Assistant ambient surfaces |
| 0.3.x | Governed coaching/progression/adaptation |

## Working rule

Before any workstream begins:

- reconcile current `origin/main`;
- inspect open PRs;
- inspect recent relevant CI/release evidence;
- read `AGENTS.md`;
- update the programme ledger;
- confirm dependencies and non-goals;
- avoid duplicating already completed work.

Chat history is context only. Repository state is authority.
