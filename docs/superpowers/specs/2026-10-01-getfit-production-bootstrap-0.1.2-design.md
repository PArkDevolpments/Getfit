# Getfit 0.1.2 Production Bootstrap Design

**Status:** Approved  
**Repository:** `ktgregson93-collab/Getfit`  
**Base:** `main` at `5851dc9165871a0df7315e4aed6791e8a7d2b399`  
**Trigger:** Live Home Assistant Ingress reached Getfit successfully on 0.1.1 but returned `IDENTITY_NOT_MAPPED`.

## Problem

Getfit 0.1.1 now authenticates real Home Assistant Supervisor Ingress correctly, but a cold production database contains no stable people, no external identity mappings, no imported programme, and no person-programme assignments. Tests create those records explicitly, so the production cold-start path was not covered by the release gate.

The live failure is therefore not a single bad Home Assistant user ID. The runtime is missing a complete, idempotent production bootstrap path.

## Goals

1. Preserve fail-closed production identity: no guessed Home Assistant user IDs, no display-name matching, no cross-person fallback.
2. Make the Home Assistant app configurable with explicit stable HA user IDs for Kris and Kirsty.
3. Make an authenticated but unmapped user see a safe setup page that reveals only their own Home Assistant stable user ID and clear configuration guidance.
4. Idempotently create the approved Getfit identities and their external mappings.
5. Idempotently import the existing approved Foundation Week 1 programme using the current deterministic seed importer.
6. Idempotently create active person-programme assignments for configured people.
7. Preserve `/data` and all existing workout/draft/history records across upgrades and restarts.
8. Cover a true production cold start in permanent E2E acceptance.
9. Release as `0.1.2` only after the full CI, migration, Docker, multi-arch publish, and anonymous-pull gates succeed.

## Non-goals

- Do not guess, infer, or auto-discover Home Assistant user IDs from display names.
- Do not create fallback mappings from Kirsty to Kris or vice versa.
- Do not activate or mutate Pep Health.
- Do not mutate Menu-Nutrition.
- Do not invent missing 52-week programme content; 0.1.2 bootstraps only the approved production seed currently present.
- Do not wipe, recreate, or replace the persistent production database.
- Do not expose another person's Home Assistant ID on an unmapped-user screen.

## Configuration contract

The Home Assistant app gains two optional admin-owned string options:

- `kris_ha_user_id`
- `kirsty_ha_user_id`

Empty values mean that person is not mapped for Home Assistant access. The app must not substitute a different identity when an option is empty.

Existing equipment options remain unchanged.

At startup, `run.sh` reads Home Assistant app options from `/data/options.json` and exports only the validated bootstrap values needed by the Python runtime. The stable HA user IDs are configuration data, not browser/client input.

## Stable identity bootstrap

A new bootstrap service owns deterministic creation/update validation for the two approved Getfit people:

### Kris

- Getfit person ID: `hwa-kris`
- canonical key: `kris`
- display name: `Kris`
- presentation profile: `male`
- Pep: `person_a`
- Health: `kris`
- Menu: `person_1`
- Home Assistant: value from `kris_ha_user_id` when configured

### Kirsty

- Getfit person ID: `hwa-kirsty`
- canonical key: `kirsty`
- display name: `Kirsty`
- presentation profile: `female`
- Pep: `person_b`
- Health: `kirsty`
- Menu: `person_2`
- Home Assistant: value from `kirsty_ha_user_id` when configured

Bootstrap is idempotent. If a stable person already exists with the approved identity, replay performs no destructive mutation. If an existing authority mapping conflicts with the configured subject, startup fails closed with an explicit bootstrap conflict rather than silently reassigning identity.

The database uniqueness rules remain the authority for one external subject per authority and one mapping per authority per person.

## Unmapped-user setup experience

Ingress authentication remains unchanged and still requires the trusted Supervisor peer.

After successful Ingress authentication, if the Home Assistant subject has no Getfit mapping, web navigation returns an HTML setup page rather than raw JSON. The page may display:

- a clear `Getfit setup required` message;
- the current authenticated user's own Home Assistant stable user ID;
- instructions to paste that value into either the Kris or Kirsty option in the Home Assistant Getfit app configuration and restart the app.

It must not display:

- another user's ID;
- Pep, Health, or Menu identifiers;
- tokens, endpoints, secrets, or internal database IDs.

API endpoints retain fail-closed machine-readable errors; only the browser product surface gets the setup presentation.

## Programme bootstrap

The existing `import_week_seed()` service remains authoritative for immutable programme import. Production startup calls it after people are present, using:

- `programme_seed/home-workout-12m-v1/programme.json`
- `programme_seed/home-workout-12m-v1/week-01.json`

The existing checksum and replay-safety behavior is preserved. Seed conflicts remain hard failures and are never overwritten automatically.

No new training prescription is introduced by bootstrap.

## Person-programme assignments

After successful programme import, each configured approved person receives one active assignment to `home-workout-12m-v1` when no active assignment exists.

Assignment creation must be deterministic/idempotent and must not duplicate active assignments across restarts. Existing completed workouts, drafts, prescription overrides, progression, and history are not rewritten.

The assignment `effective_from_utc` is created once at bootstrap time and then preserved.

## Startup ordering

Production startup sequence becomes:

1. Validate `/data` and database URL as today.
2. Run Alembic migrations to `head`.
3. Parse Home Assistant app options.
4. Open the production database.
5. Bootstrap approved people and configured Home Assistant mappings.
6. Import/replay the approved Week 1 programme seed.
7. Create/replay active programme assignments for configured people.
8. Start Uvicorn with proxy rewriting still disabled so the Supervisor socket peer remains trustworthy.

Any identity or seed conflict fails startup visibly rather than starting with ambiguous authority.

## Persistence and upgrade behavior

All bootstrap writes occur inside the existing persistent SQLite database under `/data`. Updating from 0.1.1 to 0.1.2 keeps the same database file.

Bootstrap is additive and replay-safe:

- no table drop/recreate;
- no deletion of workout evidence;
- no deletion of drafts;
- no rewrite of immutable completed revisions;
- no replacement of an already-mapped HA identity with a different one;
- no re-import of a changed seed under the same programme identity.

## Runtime wiring

`src/hwa/runtime.py` remains the production composition root. It gains bootstrap invocation before `create_app()` finishes production construction.

The general `create_app()` factory stays test-injectable and must not silently seed identities when used by unit/integration tests. Production bootstrap is explicit in the production runtime path only.

## Testing strategy

Implementation is TDD-first.

Permanent tests must cover:

1. Empty migrated DB + configured Kris HA ID → Kris, Pep/Health/Menu mappings, Week 1 seed, and active assignment are created.
2. Same bootstrap replay → no duplicate people, mappings, programme, overrides, or assignments.
3. Conflicting HA mapping → fail closed; no silent reassignment.
4. Only Kris configured → Kirsty exists as approved stable person if needed by the seed, but has no guessed Home Assistant mapping and cannot authenticate as Kris.
5. Browser request from authenticated unmapped HA subject → setup HTML containing only that subject's stable HA ID.
6. API request from unmapped subject → existing machine-readable identity failure remains fail closed.
7. Production cold-start E2E: migrate empty DB, bootstrap configured Kris, open Today via trusted Ingress, see Kris Week 1 Day 1, start a workout, persist a draft, restart app/runtime against the same DB, and resume the same draft.
8. Existing 0.1.1-style database with workout evidence survives bootstrap unchanged.
9. Home Assistant package contract includes the two new options and version `0.1.2`.
10. Release gate still builds the production Docker image and verifies multi-arch publication/pull.

## Release and live verification

0.1.2 is not considered production-ready until the exact head passes:

- Ruff
- mypy
- unit tests
- integration tests
- contract tests
- E2E tests
- Alembic migration smoke
- production Docker build
- merge to `main`
- multi-arch GHCR publication
- anonymous pull verification for amd64 and aarch64

After publication, the live Home Assistant verification is:

1. Update Getfit to 0.1.2.
2. Open Getfit while unmapped and confirm setup page shows the current HA user ID.
3. Enter that ID into the correct person option in Getfit configuration.
4. Restart Getfit.
5. Open Ingress and confirm the correct person-scoped Today page appears.
6. Start a workout and confirm server-side draft creation.
7. Restart the app and confirm the same person's draft resumes.
8. Confirm no cross-person fallback or exposure.

## Safety / authority invariants

- Home Assistant identity is accepted only from trusted Supervisor Ingress.
- HA IDs are explicit admin-owned configuration, never guessed.
- Browser query/header identity selectors remain rejected.
- Kris and Kirsty remain separate stable people.
- Pep/Health/Menu mappings remain the approved fixed mappings above.
- Getfit remains workout authority only.
- Pep Health activation remains separate and unchanged.
- Bootstrap never grants mutation authority to Pep or Menu integrations.
