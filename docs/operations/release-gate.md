# Getfit production release gate

A Getfit production release is allowed only from the exact commit that passed every gate below. Do not publish or install a different head and do not treat an earlier green run as evidence for a later commit.

## Exact-head quality gate

The candidate exact-head commit must pass, from a clean checkout:

- `uv sync --dev`
- `uv run ruff check .`
- `uv run mypy src`
- `uv run pytest tests/unit -q`
- `uv run pytest tests/integration -q`
- `uv run pytest tests/contract -q`
- `uv run pytest tests/e2e -q`
- `rm -f hwa.db && uv run alembic upgrade head`
- `docker build -t getfit-release-candidate .`

The GitHub CI workflow is permanent release evidence for these checks. A release must not be cut while any required job is pending, skipped unexpectedly or failing.

## Whole-product acceptance

Before publication, permanent QA must prove:

1. **Kris training journey** — Today can start an approved workout; autosave preserves strength/cardio draft evidence; restart resumes the same server-owned draft; completion creates immutable evidence; Progress/History shows the completed session; the Pep workout provider exposes the effective workout revision.
2. **Kirsty isolation** — Kirsty resolves only to Kirsty, never inherits Kris's active draft, display state, authority IDs or browser-selected identity, and cannot read Kris-owned workout evidence.
3. **Corrections and export** — correction creates a later immutable revision; the earlier revision remains historical; only the latest effective revision is projected to Pep, with `supersedes_revision_number` and the effective atomic evidence ID.
4. **Restart recovery** — persistent `/data/hwa.db` survives application restart and Alembic migration startup without discarding an active draft or completed history.
5. **Home Assistant identity** — Supervisor Ingress identity is accepted only from the trusted ingress source; direct spoofed identity headers and unmapped users fail closed.
6. **Degraded dependencies** — unavailable Pep Health or Menu-Nutrition context must not block the authoritative Getfit workout flow. Missing physiological evidence remains `UNAVAILABLE`; it is never estimated. Missing optional technique/media context must degrade without loss of workout data.
7. **Responsive/touch use** — the five primary surfaces (Today, Workout, Progress, Library, Settings) retain the mobile viewport contract and primary/live controls provide at least 44 px touch targets.
8. **Equipment semantics** — treadmill supports speed/incline up to the configured installation limit; spin bike supports cadence/resistance and never exposes incline; adjustable dumbbells do not acquire cardio fields.

## Home Assistant package gate

The release commit must contain:

- root `repository.yaml`;
- `getfit/config.yaml` with the release version;
- `image: ghcr.io/ktgregson93-collab/getfit`;
- Supervisor Ingress enabled on internal port `8099`;
- production startup through `run.sh` using `/data`, migrations before Uvicorn, and `hwa.runtime:app`;
- a container image that builds successfully from the same exact-head commit.

The published container tag must exactly match `getfit/config.yaml` `version`. Verify that the GHCR tag is publicly pullable before calling the release installable.

## Production publication and install

After the exact-head gate is green:

1. Merge the exact reviewed head to `main`.
2. Publish the matching multi-architecture GHCR image for the version in `getfit/config.yaml`.
3. Verify the image/tag exists and is publicly pullable.
4. Add `https://github.com/ktgregson93-collab/Getfit` as a custom Home Assistant app repository if it is not already present.
5. Install or update Getfit through Home Assistant, preserving a cold backup of app data for significant upgrades.
6. Start Getfit and verify startup migrations, authenticated person identity, Settings equipment capability, active-draft recovery and completed workout history.
7. Open Getfit through Home Assistant Ingress and perform one non-destructive smoke check for each primary surface.

Do not call the instance live until the Home Assistant-side install/update and post-start smoke verification have actually succeeded.

## Authority boundary

Publishing Getfit does **not** activate Pep Health as a progression authority and does not grant Pep-Site or Menu-Nutrition mutation authority. Read-only presentation context and the versioned workout-source export remain within their approved contracts. Any new LIVE Pep Health activation, cross-system mutation or changed authority relationship requires separate explicit approval and its own acceptance evidence.
