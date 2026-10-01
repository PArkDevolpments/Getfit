# Getfit 0.1.2 Production Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a fresh or upgraded Home Assistant installation bootstrap the approved Getfit people, explicit HA identity mappings, Foundation Week 1 programme, and active assignments safely, while giving unmapped browser users a setup page and preserving fail-closed API behavior.

**Architecture:** Keep production bootstrap explicit in `hwa.runtime`, never in the generic `create_app()` factory. A focused bootstrap service owns stable people/mappings/programme assignments and reuses the existing immutable `import_week_seed()` importer. Browser routes use a web-only identity dependency that turns a valid-but-unmapped Supervisor principal into a setup-page exception; API dependencies remain unchanged and machine-readable.

**Tech Stack:** Python 3.12, FastAPI/Starlette, SQLAlchemy 2, Pydantic 2, Alembic, Jinja2, Home Assistant App configuration/bashio, pytest, Ruff, mypy, Docker/GHCR.

**Spec:** `docs/superpowers/specs/2026-10-01-getfit-production-bootstrap-0.1.2-design.md`

## Global Constraints

- Release version is exactly `0.1.2` in Home Assistant metadata, Python package metadata, and application-reported version.
- Home Assistant identity is trusted only through the existing Supervisor Ingress provider; no client-selected identity and no display-name matching.
- HA user IDs are explicit admin-owned configuration values `kris_ha_user_id` and `kirsty_ha_user_id`; empty means unmapped.
- Approved fixed mappings remain Kris → Pep `person_a`, Health `kris`, Menu `person_1`; Kirsty → Pep `person_b`, Health `kirsty`, Menu `person_2`.
- Never fall back from Kirsty to Kris or vice versa.
- Reuse only `programme_seed/home-workout-12m-v1/programme.json` and `programme_seed/home-workout-12m-v1/week-01.json`; do not invent later weeks.
- Preserve `/data` and the existing SQLite DB; no table recreation, history rewrite, or evidence deletion.
- Production Uvicorn must retain `--no-proxy-headers` so `request.client.host` remains the Supervisor socket peer.
- Pep Health activation and Menu mutation remain out of scope.

## Review Focus

- **Whitespace/empty HA option values:** treat `""` or whitespace-only IDs as unconfigured; never create an empty HOME_ASSISTANT mapping. Covered in Task 1 and Task 2 tests.
- **Duplicate HA subject configured for both people:** fail startup with `BootstrapConflictError`; never let uniqueness errors partially choose a person. Covered in Task 2.
- **Existing person or authority mapping with conflicting approved identity:** fail closed before silent reassignment. Covered in Task 2.
- **Existing same-seed programme plus historical workouts/drafts:** bootstrap must add only missing assignment/mappings and leave historical rows unchanged. Covered in Task 4.
- **Authenticated unmapped browser request to any product route:** render only that principal's own HA subject on setup HTML while `/api/*` remains JSON 403. Covered in Task 5.

---

### Task 1: Home Assistant bootstrap configuration and version alignment

**Files:**
- Modify: `getfit/config.yaml`
- Modify: `run.sh`
- Modify: `pyproject.toml`
- Modify: `src/hwa/main.py`
- Modify: `tests/contract/test_home_assistant_package.py`
- Test: `tests/unit/test_runtime.py`

**Interfaces:**
- Consumes: existing Home Assistant app options and `bashio::config` runtime export pattern.
- Produces: environment values `HWA_KRIS_HA_USER_ID` and `HWA_KIRSTY_HA_USER_ID`; application/package/app version `0.1.2`.

- [ ] **Step 1: Extend the package contract tests for 0.1.2 and identity options**

Add assertions that `getfit/config.yaml` has version `0.1.2`, options `kris_ha_user_id: ""` and `kirsty_ha_user_id: ""`, matching string schema entries, and that `run.sh` exports both values before starting Uvicorn while retaining `--no-proxy-headers`.

- [ ] **Step 2: Run the focused contract test and verify RED**

Run: `pytest tests/contract/test_home_assistant_package.py -q`

Expected: FAIL because version/options/runtime exports are still 0.1.1/missing.

- [ ] **Step 3: Add runtime parsing tests for optional IDs**

In `tests/unit/test_runtime.py`, add tests for `build_production_bootstrap_config()` asserting:

```python
assert config.kris_ha_user_id == "ha-user-kris"
assert config.kirsty_ha_user_id is None
```

and whitespace-only input normalizes to `None`.

- [ ] **Step 4: Implement configuration/version changes**

In `getfit/config.yaml`, add the two empty string options/schema entries and set version to `0.1.2`.

In `run.sh`, export:

```bash
HWA_KRIS_HA_USER_ID
HWA_KIRSTY_HA_USER_ID
```

from `bashio::config`, without changing database location or the existing Uvicorn trust flags.

In `src/hwa/main.py`, set `APP_VERSION = "0.1.2"`.

In `pyproject.toml`, set project version to `0.1.2`.

- [ ] **Step 5: Add `build_production_bootstrap_config() -> ProductionBootstrapConfig` to `src/hwa/runtime.py`**

It reads only the two `HWA_*_HA_USER_ID` environment variables and normalizes missing/whitespace-only values to `None`. The `ProductionBootstrapConfig` type is introduced in Task 2; for RED→GREEN sequencing, Task 1 may temporarily import the not-yet-implemented type only after Task 2 begins, or Task 1 and Task 2 may be committed together if required by import collection.

- [ ] **Step 6: Verify focused tests GREEN**

Run: `pytest tests/contract/test_home_assistant_package.py tests/unit/test_runtime.py -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add getfit/config.yaml run.sh pyproject.toml src/hwa/main.py src/hwa/runtime.py tests/contract/test_home_assistant_package.py tests/unit/test_runtime.py
git commit -m "feat: add Getfit bootstrap configuration"
```

---

### Task 2: Stable people and external identity bootstrap

**Files:**
- Create: `src/hwa/services/production_bootstrap.py`
- Create: `tests/unit/services/test_production_bootstrap.py`

**Interfaces:**
- Produces:
  - `ProductionBootstrapConfig(kris_ha_user_id: str | None, kirsty_ha_user_id: str | None)`
  - `BootstrapConflictError(RuntimeError)`
  - `BootstrapResult(people_created: int, mappings_created: int, assignments_created: int, programme_changed: bool)`
  - `bootstrap_production(session: Session, config: ProductionBootstrapConfig, manifest_path: Path, week_path: Path, *, now: datetime | None = None) -> BootstrapResult`
- Consumes: `Person`, `ExternalIdentityMapping`, existing SQLAlchemy uniqueness constraints.

- [ ] **Step 1: Write RED tests for approved stable people and fixed authority mappings**

Test empty DB + `ProductionBootstrapConfig("ha-kris", None)` eventually creates:

```python
Person(id="hwa-kris", canonical_key="kris", display_name="Kris", presentation_profile="male")
Person(id="hwa-kirsty", canonical_key="kirsty", display_name="Kirsty", presentation_profile="female")
```

with Kris mappings `HOME_ASSISTANT=ha-kris`, `PEP_SITE=person_a`, `HEALTH_PROFILE=kris`, `MENU_NUTRITION=person_1`; Kirsty gets only fixed non-HA mappings when her HA option is unconfigured.

- [ ] **Step 2: Add RED conflict tests**

Cover:

```python
ProductionBootstrapConfig("same-ha-id", "same-ha-id")
```

raising `BootstrapConflictError`, plus an existing `hwa-kris` HOME_ASSISTANT mapping to a different subject raising the same error without reassignment.

Also cover an existing `Person` with ID/canonical key but conflicting display/profile data.

- [ ] **Step 3: Run RED**

Run: `pytest tests/unit/services/test_production_bootstrap.py -q`

Expected: FAIL because `hwa.services.production_bootstrap` does not exist.

- [ ] **Step 4: Implement deterministic people/mapping ensure helpers**

In `src/hwa/services/production_bootstrap.py`, keep approved person specs as immutable module constants and implement private helpers that:

- query by stable person ID and canonical key;
- create when absent;
- validate exact approved metadata when present;
- validate both `(person_id, authority)` and `(authority, external_subject_id)` before adding a mapping;
- never update a conflicting mapping in place;
- use deterministic mapping IDs derived from stable person + authority.

`BootstrapConflictError` must carry a stable explanatory message without secrets.

- [ ] **Step 5: Verify identity-focused tests GREEN**

Run: `pytest tests/unit/services/test_production_bootstrap.py -q -k "identity or mapping or conflict or duplicate"`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/hwa/services/production_bootstrap.py tests/unit/services/test_production_bootstrap.py
git commit -m "feat: bootstrap stable Getfit identities"
```

---

### Task 3: Programme import and active assignment bootstrap

**Files:**
- Modify: `src/hwa/services/production_bootstrap.py`
- Modify: `tests/unit/services/test_production_bootstrap.py`
- Test: `tests/integration/test_production_bootstrap.py`

**Interfaces:**
- Consumes: `import_week_seed(session, manifest_path, week_path) -> SeedImportResult`, `ProgrammeDefinition`, `PersonProgrammeAssignment`.
- Produces: completed `bootstrap_production(...) -> BootstrapResult` contract from Task 2.

- [ ] **Step 1: Write RED integration test for empty DB cold bootstrap**

Create an empty migrated/test-schema DB, call `bootstrap_production(...)` with Kris configured, and assert:

- programme `home-workout-12m-v1` exists;
- exactly four Week 1 programme days exist;
- the existing Kris prescription overrides from `week-01.json` were imported;
- Kris has exactly one `ACTIVE` assignment;
- Kirsty has no assignment when her HA ID is unconfigured.

- [ ] **Step 2: Write replay/idempotency RED test**

Call bootstrap twice with the same `now`. Capture counts of `people`, `external_identity_mappings`, `programme_definitions`, `programme_days`, `person_prescription_overrides`, and `person_programme_assignments`; assert the second call leaves counts unchanged and preserves the first assignment's `effective_from_utc`.

- [ ] **Step 3: Write both-configured assignment test**

With both HA IDs configured, assert exactly one active assignment per person to `home-workout-12m-v1`.

- [ ] **Step 4: Run RED**

Run: `pytest tests/integration/test_production_bootstrap.py -q`

Expected: FAIL because programme/assignment orchestration is not yet implemented.

- [ ] **Step 5: Implement programme and assignment orchestration**

After identity validation succeeds, `bootstrap_production(...)` must:

1. call `import_week_seed(session, manifest_path, week_path)` exactly once per bootstrap invocation;
2. for each person whose HA ID is configured, query active assignment to `home-workout-12m-v1`;
3. create a deterministic assignment ID only when absent;
4. set `effective_from_utc` to supplied `now` or `datetime.now(UTC)` only on first creation;
5. preserve existing active assignment unchanged;
6. commit assignment additions without modifying workout/draft/history tables.

- [ ] **Step 6: Verify GREEN**

Run: `pytest tests/unit/services/test_production_bootstrap.py tests/integration/test_production_bootstrap.py -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/hwa/services/production_bootstrap.py tests/unit/services/test_production_bootstrap.py tests/integration/test_production_bootstrap.py
git commit -m "feat: bootstrap approved programme assignments"
```

---

### Task 4: Explicit production runtime bootstrap and upgrade preservation

**Files:**
- Modify: `src/hwa/runtime.py`
- Modify: `tests/unit/test_runtime.py`
- Create: `tests/integration/test_runtime_bootstrap.py`

**Interfaces:**
- Consumes: `ProductionBootstrapConfig`, `bootstrap_production(...)`, `create_engine()`, `create_app(engine=...)`.
- Produces: production ASGI `app` built from the same engine that was bootstrapped.

- [ ] **Step 1: Write RED runtime composition test**

Patch the runtime database/environment to a temporary SQLite DB and assert production composition:

- uses one engine for bootstrap and `create_app`;
- bootstraps before serving requests;
- uses the exact seed paths under `/app/programme_seed/home-workout-12m-v1/` in the container/runtime contract;
- leaves `create_app()` by itself non-seeding.

- [ ] **Step 2: Write existing-data preservation test**

Seed an existing valid person/programme/assignment plus a completed workout event or active draft, run bootstrap, then assert the historical row IDs/revisions/draft payload are byte-for-value equivalent afterward.

- [ ] **Step 3: Run RED**

Run: `pytest tests/unit/test_runtime.py tests/integration/test_runtime_bootstrap.py -q`

Expected: FAIL because runtime does not invoke production bootstrap.

- [ ] **Step 4: Implement runtime composition**

Refactor `src/hwa/runtime.py` to:

```python
def build_production_app() -> FastAPI: ...
app = build_production_app()
```

`build_production_app()` must create one engine, open one bootstrap `Session`, call `bootstrap_production(...)`, then call `create_app(engine=engine, equipment_profile=...)`. Do not modify generic `create_app()` to seed data.

Use paths resolved relative to installed `/app/programme_seed` or an explicit production seed-root constant that tests can override; do not rely on browser working directory.

- [ ] **Step 5: Verify runtime and preservation GREEN**

Run: `pytest tests/unit/test_runtime.py tests/integration/test_runtime_bootstrap.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/hwa/runtime.py tests/unit/test_runtime.py tests/integration/test_runtime_bootstrap.py
git commit -m "feat: bootstrap Getfit production runtime"
```

---

### Task 5: Safe browser setup page for authenticated unmapped users

**Files:**
- Create: `src/hwa/web/dependencies.py`
- Create: `src/hwa/web/setup.py`
- Create: `src/hwa/web/templates/setup_required.html`
- Modify: `src/hwa/web/router.py`
- Modify: `src/hwa/main.py`
- Create: `tests/integration/web/test_setup_required.py`
- Modify: `tests/contract/test_me_api.py`

**Interfaces:**
- Consumes: existing `PrincipalProvider.resolve(request) -> AuthenticatedPrincipal`, `IdentityService.resolve(principal) -> PersonContext`, `IdentityNotMappedError`.
- Produces:
  - `WebIdentitySetupRequired(subject_id: str)`
  - `resolve_web_person_context(request: Request) -> PersonContext`
  - `setup_required_exception_handler(request: Request, exc: WebIdentitySetupRequired) -> HTMLResponse`
- API `resolve_person_context()` in `hwa.api.dependencies` remains unchanged.

- [ ] **Step 1: Write RED browser test for unmapped trusted principal**

Using `StaticPrincipalProvider("real-ha-user-id")` with no HOME_ASSISTANT mapping, request `/` and assert:

```python
assert response.status_code == 403
assert "Getfit setup required" in response.text
assert "real-ha-user-id" in response.text
assert "person_a" not in response.text
assert "person_b" not in response.text
assert "person_1" not in response.text
```

Also request `/settings` and assert the same setup presentation, proving all product routes use the web dependency.

- [ ] **Step 2: Pin API behavior separately**

Extend `tests/contract/test_me_api.py` so `/api/v1/me` with the same unmapped principal remains JSON 403 with `IDENTITY_NOT_MAPPED` and does not render HTML.

- [ ] **Step 3: Run RED**

Run: `pytest tests/integration/web/test_setup_required.py tests/contract/test_me_api.py -q`

Expected: browser test fails with existing JSON 403 while API contract still passes.

- [ ] **Step 4: Implement web-only identity dependency and exception**

`resolve_web_person_context()` performs the same authentication/identity resolution as the API dependency, but on `IdentityNotMappedError` raises `WebIdentitySetupRequired(principal.subject_id)` instead of converting it to API JSON.

Authentication failures must remain 401 and must not reveal a subject.

- [ ] **Step 5: Render setup template and register handler**

`setup_required.html` may show only the authenticated subject ID and these option names:

- `kris_ha_user_id`
- `kirsty_ha_user_id`

It must instruct the administrator to update the Getfit Home Assistant app configuration and restart. Do not include Pep/Health/Menu IDs, DB IDs, endpoints, or tokens.

Register `setup_required_exception_handler` in `create_app()` and change only web router dependencies to `resolve_web_person_context`; API routers continue using `hwa.api.dependencies.resolve_person_context`.

- [ ] **Step 6: Verify browser/API isolation GREEN**

Run: `pytest tests/integration/web/test_setup_required.py tests/contract/test_me_api.py -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/hwa/web/dependencies.py src/hwa/web/setup.py src/hwa/web/templates/setup_required.html src/hwa/web/router.py src/hwa/main.py tests/integration/web/test_setup_required.py tests/contract/test_me_api.py
git commit -m "feat: guide unmapped Home Assistant users safely"
```

---

### Task 6: Production cold-start acceptance, release gate, and 0.1.2 publication

**Files:**
- Create: `tests/e2e/test_production_cold_start.py`
- Modify: `tests/contract/test_home_assistant_package.py`
- Modify if needed: `tests/contract/test_release_publish_workflow.py`
- Modify if needed: `.github/workflows/ci.yml`
- No change expected: `.github/workflows/release.yml` unless the existing version-derivation contract fails for 0.1.2.

**Interfaces:**
- Consumes: all Tasks 1–5, existing workout draft APIs, existing release workflow.
- Produces: one exact-head release candidate proven from empty DB through restart recovery and Docker build.

- [ ] **Step 1: Write the production cold-start E2E test**

The test must use a new temporary DB and production-shaped trusted Ingress principal. Sequence:

1. migrate/schema-create empty DB;
2. bootstrap with Kris HA subject configured;
3. build/start app against that same DB;
4. GET `/` and assert `Kris`, `Week 1`, `Day 1`, and primary action `start`;
5. start Week 1 Day 1 through the real draft API/product flow;
6. assert one Kris-owned active draft exists;
7. dispose/recreate runtime/app against the same DB to simulate restart;
8. GET `/` and assert primary action `resume` and same draft ID/version;
9. assert no Kirsty fallback/data appears.

- [ ] **Step 2: Add setup-to-config acceptance**

In the same E2E module or a second test, first boot with no HA IDs and assert unmapped setup HTML reveals only the current subject; then rebuild runtime with that exact subject configured for Kris and assert Today resolves as Kris.

- [ ] **Step 3: Run E2E RED/GREEN cycle**

Run: `pytest tests/e2e/test_production_cold_start.py -q`

Expected before final fixes: FAIL at whichever cold-start/runtime path remains incomplete. After implementation: PASS.

- [ ] **Step 4: Run full local/repository verification**

Run in this order:

```bash
ruff check .
mypy src
pytest tests/unit -q
pytest tests/integration -q
pytest tests/contract -q
pytest tests/e2e -q
alembic -c alembic.ini upgrade head
```

Then build the production image using the same command/action contract used by `.github/workflows/ci.yml`.

Expected: all commands PASS; Docker image builds successfully.

- [ ] **Step 5: Open PR and require exact-head CI GREEN**

PR title: `Getfit 0.1.2: production cold-start bootstrap`

The PR body must call out the live trigger `IDENTITY_NOT_MAPPED`, identity fail-closed guarantees, no DB wipe, no Pep activation, and exact test counts/checks from the successful head.

Do not merge a head whose CI evidence belongs to an earlier SHA.

- [ ] **Step 6: Merge exact GREEN head and follow main CI**

After exact-head verification/review, merge to `main`. Require the `main` CI for the merge SHA to pass before considering release publication eligible.

- [ ] **Step 7: Follow 0.1.2 Release workflow to registry verification**

Require:

- amd64 build/publish success;
- aarch64 build/publish success;
- multi-arch manifest success;
- anonymous pull verification for both architectures.

Record the immutable `ghcr.io/ktgregson93-collab/getfit:0.1.2` manifest digest.

- [ ] **Step 8: Live Home Assistant verification**

User-facing sequence after registry verification:

1. update Home Assistant Getfit to `0.1.2`;
2. open Getfit unmapped and copy only the displayed current HA stable user ID;
3. enter it into `kris_ha_user_id` (or `kirsty_ha_user_id` for the relevant account) in App configuration;
4. restart Getfit;
5. verify person-scoped Today Week 1 Day 1;
6. start a workout and confirm autosaved draft;
7. restart Getfit and confirm Resume returns the same draft;
8. verify the other person's data is never shown.

The release is not called LIVE until these Home Assistant-side smoke checks succeed.

- [ ] **Step 9: Commit any acceptance-only changes before PR finalization**

```bash
git add tests/e2e/test_production_cold_start.py tests/contract/test_home_assistant_package.py tests/contract/test_release_publish_workflow.py .github/workflows/ci.yml
git commit -m "test: gate Getfit production cold start"
```
