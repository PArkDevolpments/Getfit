# Getfit on Home Assistant

## Runtime model

Getfit is packaged as a Home Assistant app and is intended to be opened only through Home Assistant Supervisor Ingress. The app listens internally on port `8099`; no direct host port is exposed by the package.

Production identity is resolved from Supervisor Ingress. `X-Remote-User-Id` is trusted only when the request comes from the Supervisor ingress source `172.30.32.2`. A browser or direct HTTP client cannot become another Getfit person merely by supplying that header.

## Repository installation model

The GitHub repository is structured as a Home Assistant custom app repository:

- `repository.yaml` identifies the repository to Home Assistant.
- `getfit/config.yaml` defines the Getfit app shown in the Home Assistant app store.
- `image: ghcr.io/ktgregson93-collab/getfit` points Supervisor at the published multi-architecture production image.
- The app version in `getfit/config.yaml` must match the published container tag.

Once the matching image has been published, add `https://github.com/ktgregson93-collab/Getfit` as a custom app repository in Home Assistant, install Getfit, and open it through Ingress.

The panel is intentionally not admin-only. Home Assistant supplies the authenticated stable user ID and Getfit then applies its explicit person mapping; an unmapped Home Assistant user is denied rather than falling back to another person.

## Installation equipment options

The app configuration exposes installation-level equipment capability only. Defaults reflect the approved home installation:

- treadmill available, with speed and incline up to `20%`;
- spin bike available, with cadence/resistance and no incline concept;
- adjustable dumbbells available.

`run.sh` reads the Home Assistant app options and exports them to the production runtime. The runtime validates them before starting. Invalid values fail closed instead of silently changing training capability semantics.

These options describe what equipment exists. They are not a demographic or physiological load calculator. Starting loads and progression still come from approved targets, individual calibration and performed evidence.

## Full-canvas iPhone panel

The Supervisor app remains the runtime and identity boundary, but a matching optional Home Assistant custom integration can replace the narrow built-in app frame with Getfit's full-canvas panel host. This avoids granting the Getfit app write access to `/config` merely to install UI files.

See [Getfit Full-Canvas Home Assistant Panel](getfit-full-canvas-panel.md) for installation, verification and rollback. The app continues to use Supervisor Ingress; do not expose port 8099 directly as a workaround for mobile layout.

## Persistent data

The app starts in `/data`. The default SQLite URL therefore resolves to:

`/data/hwa.db`

SQLite WAL mode, foreign keys and the configured busy timeout are enabled by Getfit's database engine. Active workout drafts and immutable completed/corrected workout evidence are stored in this database.

Do not move the runtime database into `/app`; the application image is replaceable during upgrades while `/data` is the persistent app data area.

## Startup and migrations

`run.sh` performs this sequence on every app start:

1. Read and validate the Home Assistant equipment options.
2. Change to `/data`.
3. Run `alembic -c /app/alembic.ini upgrade head`.
4. Start `uvicorn hwa.runtime:app` on port `8099`.

Alembic's migration directory is anchored to the packaged `/app/alembic.ini`, while the relative SQLite URL continues to resolve inside `/data`. Re-running `upgrade head` on an already-current database is expected and must not discard an active draft.

If a migration or runtime configuration check fails, the app must not continue to Uvicorn. Investigate and recover the configuration/database before retrying rather than bypassing the startup gate.

## Backup before an update

The package requests cold backups so Home Assistant stops Getfit while its app data is captured. Before a significant Getfit image or schema update:

1. Confirm the current app is healthy and any important workout has been autosaved.
2. Create a Home Assistant backup containing Getfit app data.
3. Keep the backup until the updated app has started, migrations have completed and the active workout/draft state has been checked.

Avoid treating a casual copy of a live SQLite main file as a complete backup while WAL writes may still be active. If a manual filesystem copy is ever required, stop the app first and preserve the complete SQLite state.

## Update verification

After an app update:

1. Start Getfit through Home Assistant.
2. Confirm startup logs show Alembic reaching the current migration head without error.
3. Open Getfit through Ingress, not a direct port.
4. Confirm the authenticated person is correct.
5. Confirm Settings reports the expected treadmill, spin-bike and dumbbell capabilities.
6. If a workout was active before restart, confirm the same draft resumes with its saved version and entered state.
7. Confirm completed workout history is still present.

A package update must never create a replacement empty database simply because application code changed.

## Recovery

If the app cannot start after an update:

1. Stop Getfit.
2. Preserve the current `/data` before making repair attempts.
3. Restore the most recent known-good Home Assistant backup if the database itself was damaged or an update must be rolled back.
4. Start Getfit. The normal startup path runs `alembic upgrade head` against the restored `/data/hwa.db` before serving requests.
5. Verify person identity, active-draft resume and completed workout history before normal use.

If only the application image is rolled back, ensure the restored database schema is compatible with that image; prefer restoring the matching app-data backup rather than manually editing schema tables.

## Security boundary

Getfit's production authentication boundary is Home Assistant Supervisor Ingress plus explicit stable-user mappings. Display names and query-string person identifiers are not ownership keys. Direct spoofed identity headers fail closed.

Integration status shown in Getfit Settings does not expose tokens, endpoints or cross-system person identifiers.

## Scope

This package and runbook make the Getfit runtime repeatable and recoverable. Publishing and installation are release operations performed only after the whole-product acceptance gate is green. Pep Health activation and any Pep/Menu mutation authority remain separate governance decisions.
