# Getfit 0.1.2 Production Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a fresh or upgraded Home Assistant installation bootstrap the approved Getfit people, explicit HA identity mappings, Foundation Week 1 programme, and active assignments safely, while giving unmapped browser users a setup page and preserving fail-closed API behavior.

**Architecture:** Keep production bootstrap explicit in `hwa.runtime`, never in the generic `create_app()` factory. A focused bootstrap service owns stable people/mappings/programme assignments and reuses the existing immutable `import_week_seed()` importer. Browser routes use a web-only identity dependency that turns a valid-but-unmapped Supervisor principal into a setup-page exception; API dependencies remain unchanged and machine-readable.

**Tech Stack:** Python 3.12, FastAPI/Starlette, SQLAlchemy 2, Pydantic 2, Alembic, Jinja2, Home Assistant App configuration/bashio, pytest, Ruff, mypy, Docker/GHCR.

**Spec:** `docs/superpowers/specs/2026-10-01-getfit-production-bootstrap-0.1.2-design.md`

## Global Constraints

- Release version is exactly `0.1.2` in `getfit/config.yaml`, `pyproject.toml`, and `src/hwa/main.py`.
- Trust Home Assistant identity only through the existing Supervisor Ingress provider; never from query parameters, display names, or arbitrary client headers.
- `kris_ha_user_id` and `kirsty_ha_user_id` are explicit admin-owned options; empty/whitespace means unmapped.
- Approved mappings remain Kris → Pep `person_a`, Health `kris`, Menu `person_1`; Kirsty → Pep `person_b`, Health `kirsty`, Menu `person_2`.
- No cross-person fallback.
- Bootstrap only the existing approved `home-workout-12m-v1` Week 1 seed; do not invent Weeks 2–52.
- Preserve `/data` and existing workout/draft/history rows.
- Retain `uvicorn --no-proxy-headers` in production.
- No Pep Health activation and no Menu mutation.

## Review Focus

- Empty/whitespace HA option values must create no HOME_ASSISTANT mapping.
- The same HA subject configured for both people must fail with `BootstrapConflictError` before ambiguous identity is stored.
- Existing conflicting person metadata or authority mappings must fail closed, never be silently rewritten.
- Existing same-seed programme plus workout/draft history must survive replay unchanged.
- Any authenticated unmapped browser route must show only that principal's own HA subject, while `/api/*` stays JSON 403.

---

### Task 1: Home Assistant options and 0.1.2 version contract

**Files:**
- Modify: `getfit/config.yaml`
- Modify: `run.sh`
- Modify: `pyproject.toml`
- Modify: `src/hwa/main.py`
- Modify: `tests/contract/test_home_assistant_package.py`

**Interfaces:**
- Produces environment values `HWA_KRIS_HA_USER_ID` and `HWA_KIRSTY_HA_USER_ID` for the Python runtime.

- [ ] **Write RED package tests** asserting app/package/API version `0.1.2`, two empty string HA-ID options with string schemas, two `run.sh` exports, and continued `--no-proxy-headers`.
- [ ] **Run:** `pytest tests/contract/test_home_assistant_package.py -q` → expected FAIL on missing options/version.
- [ ] **Implement** the two options and exports; set `getfit/config.yaml`, `pyproject.toml`, and `APP_VERSION` to `0.1.2`. Read HA options after Alembic migration and before Uvicorn starts.
- [ ] **Run:** `pytest tests/contract/test_home_assistant_package.py -q` → PASS.
- [ ] **Commit:** `feat: add Getfit bootstrap configuration`.

---

### Task 2: Stable person and authority bootstrap

**Files:**
- Create: `src/hwa/services/production_bootstrap.py`
- Create: `tests/unit/services/test_production_bootstrap.py`

**Interfaces:**
- Produces `ProductionBootstrapConfig.from_raw(kris_ha_user_id: str | None, kirsty_ha_user_id: str | None) -> ProductionBootstrapConfig`.
- Produces `BootstrapConflictError(RuntimeError)`.
- Produces `IdentityBootstrapResult(people_created: int, mappings_created: int, configured_person_ids: tuple[str, ...])`.
- Produces `ensure_production_identities(session: Session, config: ProductionBootstrapConfig) -> IdentityBootstrapResult`.

- [ ] **Write RED tests** for normalization of empty/whitespace IDs, approved Kris/Kirsty stable person records, fixed Pep/Health/Menu mappings, and optional HA mapping only when configured.
- [ ] **Write RED conflict tests** for duplicate configured HA subject, existing person metadata mismatch, existing `(person, authority)` with another subject, and an external subject already owned by another person.
- [ ] **Run:** `pytest tests/unit/services/test_production_bootstrap.py -q` → FAIL because module is absent.
- [ ] **Implement** immutable approved-person specs, deterministic mapping IDs, exact-metadata validation, and preflight conflict checks before inserts. Never update conflicting identity in place.
- [ ] **Run:** `pytest tests/unit/services/test_production_bootstrap.py -q` → PASS.
- [ ] **Commit:** `feat: bootstrap stable Getfit identities`.

---

### Task 3: Approved programme import and active assignments

**Files:**
- Modify: `src/hwa/services/production_bootstrap.py`
- Modify: `tests/unit/services/test_production_bootstrap.py`
- Create: `tests/integration/test_production_bootstrap.py`

**Interfaces:**
- Consumes `import_week_seed(session, manifest_path, week_path) -> SeedImportResult`.
- Produces `BootstrapResult(people_created: int, mappings_created: int, assignments_created: int, programme_changed: bool)`.
- Produces `bootstrap_production(session: Session, config: ProductionBootstrapConfig, manifest_path: Path, week_path: Path, *, now: datetime | None = None) -> BootstrapResult`.

- [ ] **Write RED cold-bootstrap test:** empty DB + configured Kris produces two approved people, fixed mappings, four Week 1 days, existing Kris overrides, and exactly one active Kris assignment; unconfigured Kirsty gets no HA mapping/assignment.
- [ ] **Write replay test:** two calls leave counts of people, mappings, programme rows, overrides, and assignments unchanged and preserve the first assignment `effective_from_utc`.
- [ ] **Write both-configured test:** exactly one active assignment per configured person.
- [ ] **Run:** `pytest tests/integration/test_production_bootstrap.py -q` → expected FAIL.
- [ ] **Implement** orchestration: identity preflight/ensure → existing `import_week_seed()` → deterministic assignment ensure for configured people only. Use supplied `now` only when first creating an assignment.
- [ ] **Run:** `pytest tests/unit/services/test_production_bootstrap.py tests/integration/test_production_bootstrap.py -q` → PASS.
- [ ] **Commit:** `feat: bootstrap approved programme assignments`.

---

### Task 4: Explicit production runtime wiring and persistence safety

**Files:**
- Modify: `src/hwa/runtime.py`
- Modify: `tests/unit/test_runtime.py`
- Create: `tests/integration/test_runtime_bootstrap.py`

**Interfaces:**
- Consumes `ProductionBootstrapConfig.from_raw(...)`, `bootstrap_production(...)`, `create_engine()`, and `create_app(engine=...)`.
- Produces `build_production_bootstrap_config() -> ProductionBootstrapConfig`.
- Produces `build_production_app() -> FastAPI` and module-level `app = build_production_app()`.

- [ ] **Write RED config parsing tests**: env values trim whitespace; missing/blank becomes `None`; no inferred/fallback identity.
- [ ] **Write RED composition test**: one engine is used for bootstrap and app; bootstrap runs before requests; generic `create_app()` alone does not seed data.
- [ ] **Write preservation test**: existing valid completed workout/draft/history rows have identical IDs/revision/payload after bootstrap replay.
- [ ] **Run:** `pytest tests/unit/test_runtime.py tests/integration/test_runtime_bootstrap.py -q` → expected FAIL.
- [ ] **Implement** `build_production_bootstrap_config()` and `build_production_app()`. Resolve seed paths independently of browser CWD. Open a bootstrap `Session`, call `bootstrap_production`, then pass the same engine to `create_app` with the existing equipment profile.
- [ ] **Run:** focused runtime tests → PASS.
- [ ] **Commit:** `feat: bootstrap Getfit production runtime`.

---

### Task 5: Browser setup page without weakening API identity

**Files:**
- Create: `src/hwa/web/dependencies.py`
- Create: `src/hwa/web/setup.py`
- Create: `src/hwa/web/templates/setup_required.html`
- Modify: `src/hwa/web/router.py`
- Modify: `src/hwa/main.py`
- Create: `tests/integration/web/test_setup_required.py`
- Modify: `tests/contract/test_me_api.py`

**Interfaces:**
- Produces `WebIdentitySetupRequired(subject_id: str)`.
- Produces `resolve_web_person_context(request: Request) -> PersonContext`.
- Produces `setup_required_exception_handler(request: Request, exc: WebIdentitySetupRequired) -> HTMLResponse`.
- Existing API `resolve_person_context()` stays unchanged.

- [ ] **Write RED browser test** using trusted `StaticPrincipalProvider("real-ha-user-id")` with no mapping. `/` and `/settings` must return setup HTML containing `Getfit setup required` and only `real-ha-user-id`; no Pep/Health/Menu IDs.
- [ ] **Pin API behavior:** `/api/v1/me` with the same unmapped principal remains JSON 403 `IDENTITY_NOT_MAPPED`.
- [ ] **Run:** `pytest tests/integration/web/test_setup_required.py tests/contract/test_me_api.py -q` → browser RED/API GREEN.
- [ ] **Implement** a web-only resolver: authentication failures remain 401; `IdentityNotMappedError` becomes `WebIdentitySetupRequired(principal.subject_id)`.
- [ ] **Implement template/handler** explaining `kris_ha_user_id` / `kirsty_ha_user_id` configuration and restart. Do not show other IDs, endpoints, tokens, or DB identifiers.
- [ ] **Switch web router dependencies only** to `resolve_web_person_context`; leave API routers unchanged.
- [ ] **Run focused tests** → PASS.
- [ ] **Commit:** `feat: guide unmapped Home Assistant users safely`.

---

### Task 6: Production cold-start acceptance and release

**Files:**
- Create: `tests/e2e/test_production_cold_start.py`
- Modify: `tests/contract/test_home_assistant_package.py`
- Modify only if required by existing gate: `tests/contract/test_release_publish_workflow.py`, `.github/workflows/ci.yml`

**Interfaces:**
- Consumes Tasks 1–5, existing draft API/browser flow, and existing release workflow.
- Produces one exact-head candidate that can be published as `ghcr.io/ktgregson93-collab/getfit:0.1.2`.

- [ ] **Write E2E cold start:** empty DB → configured Kris bootstrap → trusted Ingress `/` shows Kris Week 1 Day 1/start → start workout → active Kris draft → rebuild app against same DB → `/` shows resume with same draft ID/version → no Kirsty data.
- [ ] **Write setup-to-config E2E:** boot with no HA IDs → own-subject setup page → rebuild with that exact subject configured for Kris → Today resolves to Kris.
- [ ] **Run:** `pytest tests/e2e/test_production_cold_start.py -q` and fix only evidence-backed failures.
- [ ] **Run full exact-head verification:** `ruff check .`, `mypy src`, unit, integration, contract, E2E, Alembic migration smoke, and the same production Docker build used by CI.
- [ ] **Open PR** titled `Getfit 0.1.2: production cold-start bootstrap`; document the live `IDENTITY_NOT_MAPPED` trigger, no DB wipe, fail-closed mapping, no Pep activation, and exact passing head SHA/checks.
- [ ] **Merge only the exact GREEN head**, then require `main` CI on the merge SHA to pass.
- [ ] **Follow release workflow** through amd64 + aarch64 publish, multi-arch manifest, and anonymous pulls; record the immutable 0.1.2 digest.
- [ ] **Live HA verification:** update to 0.1.2 → open unmapped setup page → copy own HA ID → configure correct person option → restart → verify Today → start/autosave → restart → resume same draft → confirm no cross-person exposure.
- [ ] Do not call the installation LIVE until those Home Assistant-side smoke checks pass.

## Self-Review Result

- **Spec coverage:** all approved design sections map to Tasks 1–6; no programme content beyond the approved Week 1 seed is introduced.
- **Step scan:** each task has a distinct RED→GREEN deliverable; the earlier forward-reference between runtime config and bootstrap types was removed.
- **Type consistency:** `ProductionBootstrapConfig` is created in Task 2 and consumed by Tasks 3–4; browser setup types are isolated to Task 5.
- **Review focus:** all five high-risk production inputs have explicit tests in the owning task.
- **Proportion:** the plan specifies interfaces, assertions, and commands without transcribing function bodies.
