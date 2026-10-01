# Getfit on Home Assistant

## Runtime model

Getfit is packaged as a local Home Assistant app and is intended to be opened only through Home Assistant Supervisor Ingress. The app listens internally on port `8099`; no direct host port is required by the package.

Production identity is resolved from Supervisor Ingress. `X-Remote-User-Id` is trusted only when the request comes from the configured Supervisor ingress source. A browser or direct HTTP client cannot become another Getfit person merely by supplying that header.

## Persistent data

The app starts in `/data`. The default SQLite URL therefore resolves to:

`/data/hwa.db`

SQLite WAL mode, foreign keys and the configured busy timeout are enabled by Getfit's database engine. Active workout drafts and immutable completed/corrected workout evidence are stored in this database.

Do not move the runtime database into `/app`; the application image is replaceable during upgrades while `/data` is the persistent app data area.

## Startup and migrations

`run.sh` performs this sequence on every app start:

1. Change to `/data`.
2. Run `alembic -c /app/alembic.ini upgrade head`.
3. Start `uvicorn hwa.main:app` on port `8099`.

Alembic's migration directory is anchored to the packaged `/app/alembic.ini`, while the relative SQLite URL continues to resolve inside `/data`. Re-running `upgrade head` on an already-current database is expected and must not discard an active draft.

If a migration fails, the app must not continue to Uvicorn. Investigate and recover the database before retrying rather than bypassing the migration gate.

## Backup before an update

Use the Home Assistant backup mechanism so the app's `/data` is captured consistently. Before a significant Getfit image or schema update:

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
5. If a workout was active before restart, confirm the same draft resumes with its saved version and entered state.
6. Confirm completed workout history is still present.

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

This package and runbook make the Getfit runtime repeatable and recoverable. They do not deploy the branch automatically, mutate Home Assistant configuration, activate Pep Health, or grant Getfit mutation authority over Pep-Site or Menu-Nutrition.
