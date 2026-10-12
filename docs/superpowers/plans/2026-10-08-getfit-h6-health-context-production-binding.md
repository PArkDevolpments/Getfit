# Getfit H6 Health Context Production Binding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. Keep implementation and independent review agents scoped to one task and its current diff.

**Goal:** Productionise Getfit's read-only consumption of Pep's server-owned Health Context through the H0-selected Home Assistant service/WebSocket path while keeping Getfit Health activation off by default.

**Architecture:** A trusted Supervisor Ingress principal supplies the HA user subject. Getfit signs a fresh, short-lived Ed25519 assertion and invokes `peptide_site.get_health_context` through `ws://supervisor/core/websocket`. Pep performs final HA-user-to-Pep-person resolution and returns its closed v1 projection inside the HA service response envelope. Getfit strictly validates it, holds it only for the current request, and projects approved presentation fields without gaining Health authority.

**Tech stack:** Python 3.12, FastAPI, Pydantic v2, `cryptography`, `websockets`, Home Assistant Supervisor/Core WebSocket API, pytest, Ruff, strict mypy, Docker.

**Design:** `docs/superpowers/specs/2026-10-08-getfit-h6-health-context-production-binding-design.md`

**Provider contract:** Pep-Site `f61b9644a88c5047176e87d4a7edf2939e218d32`

## Global constraints

- Pep-Site is the sole Health calculation, interpretation, readiness, progress and Journey authority.
- Getfit remains authoritative only for structured workout prescription and performed evidence.
- The assertion subject is the real HA user established by trusted Supervisor Ingress.
- Pep performs final HA-user-to-Pep-person resolution. Getfit sends no person/profile/source selector.
- No fabricated Ingress headers, browser-supplied authority, default person or Person B -> Person A fallback.
- No local/legacy Health calculation or interpretation fallback.
- Getfit Health activation is separate from Pep authority availability and defaults false.
- `automatic_action=false` and `causation_asserted=false` remain mandatory.
- No cross-request Health cache.
- No assertion, key, Supervisor token, raw Health payload or identity material in logs.
- H6 is read-only and may not mutate Pep, HA mappings, Health data, ledger or configuration.
- No dependency cycle in which Pep needs a Getfit Health read to calculate workout data.
- No LIVE deployment or activation. No H6S or H7 work.
- Every implementation task follows RED -> observed failure -> minimal GREEN -> focused regression -> independent review -> coherent commit.

## Baseline and release authority

- Getfit `origin/main`: `2dd07e7ea214fb8e54ff381e4012180b3c90e90a`; CI run `37356760555` succeeded.
- Pep `origin/main`: `f61b9644a88c5047176e87d4a7edf2939e218d32`.
- Open Getfit PR #100 changes review-capture UI/evidence only and does not overlap H6.
- Focused pre-plan baseline: 20 relevant tests passed using an explicit workspace-local pytest base temp.
- Existing reusable code: trusted Ingress principal provider, person mapping, strict Health projection models, request-scoped reader seam, presentation-only `ExternalContext`, unavailable rendering, no-selector web guard, and injectable production app factory.

---

## Task 1: Pin the provider contract and add the permanent RED boundary

**Files:**

- Create: `contracts/pep/health_context_v1.schema.json`
- Create: `contracts/pep/CONTRACT.md`
- Create: `tests/fixtures/pep_health_service_responses.py`
- Create: `tests/contract/test_h6_health_service_contract.py`
- Modify: `tests/contract/test_pep_health_reader.py`

- [ ] Copy the exact Pep v1 schema bytes from provider SHA `f61b9644a88c5047176e87d4a7edf2939e218d32` and record source repository, SHA, path and SHA-256 in `CONTRACT.md`. State that the snapshot is a consumer compatibility fixture, never mapping or Health authority.
- [ ] Add fixture builders for the HA service/WebSocket response envelope, ready projection and governed errors. Keep fixtures synthetic and free of real identities or Health data.
- [ ] Add RED tests requiring a production Health transport interface that accepts trusted HA subject plus expected local person/profile, emits no selector, and returns a fail-closed context.
- [ ] Add RED parser cases for `schema_version: true`, boolean numeric metrics, extra private fields, wrong schema/authority, mismatched person/profile, malformed envelope, missing `no-store`, and HA `success=false`.
- [ ] Prove the existing direct-HTTP reader cannot satisfy the new tests.

Run:

```powershell
uv run pytest tests/contract/test_h6_health_service_contract.py tests/contract/test_pep_health_reader.py -q --basetemp=.pytest-h6-task1
```

Expected RED: missing service client/request interface and strict envelope behavior; existing unrelated parser tests remain green.

Checkpoint: `test: pin H6 Pep Health service contract`

## Task 2: Implement private-key loading and the canonical assertion signer

**Files:**

- Create: `src/hwa/integrations/pep/service_assertion.py`
- Create: `tests/unit/integrations/pep/test_service_assertion.py`
- Modify: `pyproject.toml`

- [ ] Add explicit `cryptography` dependency compatible with Python 3.12 and the release container; do not rely on a transitive package.
- [ ] Write RED tests for exact header/claim contract, deterministic compact JSON, unpadded base64url, Ed25519 verification, 30-second lifetime, issuer/audience, matching `kid`, trusted subject, unique `jti`, and injected UTC clock/random source.
- [ ] Add rejection tests for blank subject/kid, non-finite time, invalid expiry, malformed key encoding, non-32-byte keys, symlink/non-regular/oversized key file, and group/world-readable permissions on POSIX.
- [ ] Implement a file-only production key loader. It returns an immutable signer and never exposes raw key bytes through public attributes or representations.
- [ ] Keep exactly one active signing private key and one active `kid` in Getfit at any time. Do not implement a multi-key signer, multiple active Getfit signing keys, or automatic fallback to another private key.
- [ ] Add caplog sentinels proving key, subject, assertion and `jti` do not appear on success or failure.
- [ ] Test old and new keys as separate, sequential signer configurations. Prove each signer emits only its configured `kid` and every sign call creates a fresh `jti`.
- [ ] Keep rotation overlap on the Pep verifier side only, where old and new public keys may temporarily coexist. Emergency revocation remains Pep-side public-key removal followed by Getfit Health disable/restart; Getfit never falls back to another private key.

Run:

```powershell
uv run pytest tests/unit/integrations/pep/test_service_assertion.py -q --basetemp=.pytest-h6-task2
uv run ruff check src/hwa/integrations/pep/service_assertion.py tests/unit/integrations/pep/test_service_assertion.py
uv run mypy src/hwa/integrations/pep/service_assertion.py
```

Checkpoint: `feat: add governed H6 service assertion signer`

## Task 3: Implement the one-shot Home Assistant WebSocket service client

**Files:**

- Create: `src/hwa/integrations/pep/ha_health_service.py`
- Create: `tests/unit/integrations/pep/test_ha_health_service.py`
- Modify: `pyproject.toml`

- [ ] Add an explicit supported `websockets` dependency rather than relying on `uvicorn[standard]` transitively.
- [ ] Define a narrow injectable WebSocket connector/protocol so unit tests never contact HA.
- [ ] Write RED protocol tests for `auth_required -> auth(SUPERVISOR_TOKEN) -> auth_ok -> call_service -> result` and exact command fields: domain `peptide_site`, service `get_health_context`, `service_data={assertion}`, `return_response=true`.
- [ ] Assert there is no `target`, `person_id`, `health_profile_id`, `user_id`, source/entity selector or fabricated Ingress header anywhere in the command.
- [ ] Parse only the matching command ID and require `result.response` with exact typed `status_code`, `body`, and string headers containing `Cache-Control: no-store`. Explicitly reject boolean status codes and type-confused structures.
- [ ] Bound the entire operation with one injected monotonic timeout. Close the socket on success, HA error, malformed message, timeout and cancellation; do not leave background tasks.
- [ ] Return only a small typed envelope or stable transport failure. Never propagate raw HA error messages, response bodies, exceptions or credentials.
- [ ] Prove exactly one connection and one service command per attempt, with no automatic retry.

Run:

```powershell
uv run pytest tests/unit/integrations/pep/test_ha_health_service.py -q --basetemp=.pytest-h6-task3
uv run ruff check src/hwa/integrations/pep/ha_health_service.py tests/unit/integrations/pep/test_ha_health_service.py
uv run mypy src/hwa/integrations/pep/ha_health_service.py
```

Checkpoint: `feat: call Pep Health through HA WebSocket service`

## Task 4: Bind the service envelope to the existing closed Health reader

**Files:**

- Modify: `src/hwa/integrations/pep/health_reader.py`
- Modify: `tests/contract/test_pep_health_reader.py`
- Modify: `tests/contract/test_h6_health_service_contract.py`

- [ ] Replace the default direct-HTTP assumption with the injected HA Health service client and assertion signer. Delete or make unreachable the production direct `GET /api/peptide_site/health-context` path.
- [ ] Change the read boundary to require trusted HA subject plus expected `PersonContext`; do not derive a subject from the local Pep mapping.
- [ ] Create a fresh assertion for every attempt and pass only that assertion to the service client.
- [ ] Strictly classify governed service errors: `HEALTH_AUTHORITY_DISABLED`, `SERVICE_ASSERTION_STARTUP_QUARANTINE`, `INVALID_SERVICE_ASSERTION`, `PERSON_CONTEXT_UNAVAILABLE`, `ASSERTION_RATE_LIMITED`, provider failures, timeout and generic unavailable. Do not retry any in the current request.
- [ ] Harden the existing v1 models/guards so bool/int confusion, coercible strings, invalid timestamps and extra fields fail closed while JSON Schema `number` values remain compatible with integer or float inputs where allowed.
- [ ] Preserve exact response person/profile mismatch checks as defence in depth, `automatic_action=false`, `causation_asserted=false`, and no partial metrics from unavailable/invalid projections.
- [ ] Preserve presentation-only extraction; do not calculate Health readiness, Journey, trends, BMI or recommendations.
- [ ] Add sequential Person A then Person B tests proving the second call uses only the second trusted HA subject and no first-person context survives failure.

Run:

```powershell
uv run pytest tests/contract/test_pep_health_reader.py tests/contract/test_h6_health_service_contract.py tests/unit/domain/test_external_context.py -q --basetemp=.pytest-h6-task4
uv run ruff check src/hwa/integrations/pep/health_reader.py tests/contract
uv run mypy src/hwa/integrations/pep/health_reader.py
```

Checkpoint: `feat: consume governed Pep Health service envelope`

## Task 5: Carry the trusted principal into request-scoped Health reads

**Files:**

- Modify: `src/hwa/web/dependencies.py`
- Modify: `src/hwa/web/router.py`
- Modify: `src/hwa/main.py`
- Modify: `tests/unit/test_ha_ingress_principal.py`
- Modify: `tests/e2e/test_ingress_identity.py`
- Modify: `tests/integration/web/test_context_degradation.py`
- Create: `tests/integration/web/test_h6_health_identity.py`

- [ ] Add RED tests that only a principal resolved by the configured production provider can reach the signer. Store the resolved principal in server-side request state during the existing dependency; never copy it into template/browser state.
- [ ] Pass `AuthenticatedPrincipal.subject_id` to the Health reader and the already-resolved `PersonContext` only for response isolation validation.
- [ ] Keep all browser identity selectors rejected and prove query/header/form attempts cannot choose the assertion subject.
- [ ] Update test fakes to the new reader boundary without weakening existing person/profile assertions.
- [ ] Prove direct spoofed Ingress requests remain rejected, mapped users stay isolated, and a failed second-person read cannot display the first person's Health values or identities.
- [ ] Prove workout navigation, draft start/resume and completion remain available when Health is disabled, timed out or invalid.

Run:

```powershell
uv run pytest tests/unit/test_ha_ingress_principal.py tests/e2e/test_ingress_identity.py tests/integration/web/test_context_degradation.py tests/integration/web/test_h6_health_identity.py -q --basetemp=.pytest-h6-task5
```

Checkpoint: `feat: bind H6 reads to trusted ingress principal`

## Task 6: Add default-off production configuration and safe key materialisation

**Files:**

- Modify: `src/hwa/runtime.py`
- Modify: `src/hwa/main.py`
- Modify: `getfit/config.yaml`
- Modify: `run.sh`
- Modify: `tests/unit/test_runtime_configuration.py`
- Modify: `tests/e2e/test_production_cold_start.py`

- [ ] Add options `pep_health_enabled` (default false), `pep_health_signing_kid` and masked `pep_health_signing_private_key`. Do not reuse the Pep workout bridge token or person allow-list.
- [ ] Add `homeassistant_api: true`; do not add `hassio_api`, admin/full-access, host networking or unrelated privileges.
- [ ] In `run.sh`, set a restrictive umask, materialise the configured private key under `/data`, and export only its path plus non-secret activation/kid settings. Never echo the secret.
- [ ] In runtime construction, distinguish disabled from unavailable configuration. Disabled performs no key or token validation and constructs an explicitly disabled reader. Enabled requires a valid key, `kid` and `SUPERVISOR_TOKEN`; invalid configuration constructs an unavailable reader with `PEP_HEALTH_CONFIGURATION_INVALID` while preserving workout availability.
- [ ] Read and remove `SUPERVISOR_TOKEN` from the process environment after constructing the client configuration; retain it only inside the private client object.
- [ ] Wire a finite end-to-end timeout and the one-shot service reader into `create_app`. Keep dependency injection available for tests.
- [ ] Add cold-start tests for default-off, enabled-valid, enabled-missing-token, enabled-invalid-key and restart behavior. Assert no Health context is retained between app instances.
- [ ] Assert configuration files mask the private key, activation stays false, and no private key or token enters static/browser assets.

Run:

```powershell
uv run pytest tests/unit/test_runtime_configuration.py tests/e2e/test_production_cold_start.py -q --basetemp=.pytest-h6-task6
uv run ruff check src/hwa/runtime.py src/hwa/main.py tests/unit/test_runtime_configuration.py tests/e2e/test_production_cold_start.py
uv run mypy src
```

Checkpoint: `feat: wire default-off H6 production configuration`

## Task 7: Prove failure, privacy, lifecycle and dependency-cycle invariants

**Files:**

- Create: `tests/integration/test_h6_health_failure_matrix.py`
- Create: `tests/e2e/test_h6_health_privacy_and_isolation.py`
- Modify: `tests/integration/web/test_context_degradation.py`
- Modify: `tests/e2e/test_full_training_journey.py`

- [ ] Add the complete governed matrix: Getfit disabled; Pep disabled; startup quarantine with bounded `Retry-After`; invalid assertion; unavailable person; rate limit; rebuild timeout; overload; compute/integrity failure; socket refusal; auth failure; malformed frames; operation timeout; cancellation.
- [ ] Assert every failure is request-scoped unavailable, creates no cache, performs no local/legacy Health interpretation and leaves workouts usable.
- [ ] Assert `HEALTH_AUTHORITY_DISABLED` has no retry guidance and cannot retain a prior success. Assert quarantine/rate-limit metadata is bounded but does not sleep or retry the current request.
- [ ] Run success/failure/person-switch sequences and assert zero cross-person values or identifiers in HTML, state, logs and subsequent requests.
- [ ] Use secret/assertion/identity/Health-payload sentinels and assert none appear in logs across all exit paths.
- [ ] Instrument the service client and workout export boundary to prove a Health read makes exactly one outbound HA service call and never invokes Getfit workout services recursively.
- [ ] Prove every socket closes and no asyncio task remains after success, failure, timeout or cancellation.

Run:

```powershell
uv run pytest tests/integration/test_h6_health_failure_matrix.py tests/e2e/test_h6_health_privacy_and_isolation.py tests/integration/web/test_context_degradation.py tests/e2e/test_full_training_journey.py -q --basetemp=.pytest-h6-task7
```

Checkpoint: `test: lock H6 failure and privacy invariants`

## Task 8: Add target HA/Supervisor compatibility evidence without LIVE access

**Files:**

- Create: `_tools/qa_h6_ha_websocket_contract.py`
- Create: `_tools/tests/test_qa_h6_ha_websocket_contract.py`
- Create: `docs/superpowers/evidence/2026-10-08-getfit-h6-contract-evidence.md`
- Modify: `.github/workflows/ci.yml`

### Target HA Core image evidence

- [ ] Build a sanitized protocol probe that can target the pinned HA Core image used by Pep verification. It may emit only version/build identity, pass/fail state, stable failure class and booleans for command/envelope invariants.
- [ ] Install the Pep component from provider SHA `f61b9644a88c5047176e87d4a7edf2939e218d32` in that target Core image and prove `peptide_site.get_health_context` service registration.
- [ ] Using synthetic identities and keys only, prove HA WebSocket `call_service` with `return_response=true` reaches the service and returns the governed `{status_code, body, headers}` envelope.
- [ ] Do not claim that a plain HA Core image proves the Supervisor proxy URL or Supervisor token flow.

### Supervisor-proxy proof

- [ ] In deterministic CI, run the client against a protocol/proxy harness that proves Getfit selects exactly `ws://supervisor/core/websocket`, authenticates with `SUPERVISOR_TOKEN`, sends the governed `call_service` command, and parses its response. Do not include secrets or payloads in artifacts.
- [ ] Retain and reference the existing H0 transport evidence where its Supervisor proxy findings remain applicable; do not reinterpret Core-image evidence as Supervisor evidence.

### Pre-LIVE topology gate

- [ ] Record exact Getfit/Pep/HA image SHAs or digests, commands, workflow URLs and results in the evidence file.
- [ ] Keep representative deployed Supervisor + Getfit + Pep topology proof as a separate pre-LIVE L1 gate. If no representative staging Supervisor is available, record the limitation; do not substitute LIVE access.

Run:

```powershell
uv run pytest _tools/tests/test_qa_h6_ha_websocket_contract.py -q --basetemp=.pytest-h6-task8
uv run python _tools/qa_h6_ha_websocket_contract.py --help
```

Checkpoint: `test: add H6 HA WebSocket compatibility gate`

## Task 9: Release verification and review

**Files:**

- Modify: `README.md`
- Modify: `getfit/DOCS.md`
- Modify: `docs/superpowers/evidence/2026-10-08-getfit-h6-contract-evidence.md`
- Modify: `pyproject.toml` version and `getfit/config.yaml` version only if repository release policy requires a versioned H6 capability build

- [ ] Document default-off activation, unavailable behavior, key-file boundary, rotation/revocation sequence, Supervisor permission, rollback and explicit LIVE exclusion. Never include real keys, subjects, mappings or payloads.
- [ ] Run focused H6 tests, then the exact required CI commands:

```powershell
uv sync --dev
uv run ruff check .
uv run mypy src
uv run pytest tests/unit -q --basetemp=.pytest-h6-unit
uv run pytest tests/integration -q --basetemp=.pytest-h6-integration
uv run pytest tests/contract -q --basetemp=.pytest-h6-contract
uv run pytest tests/e2e -q --basetemp=.pytest-h6-e2e
Remove-Item -LiteralPath hwa.db -ErrorAction SilentlyContinue
uv run alembic upgrade head
docker build -t getfit-h6-ci .
```

- [ ] Run whole-branch architecture/security/privacy review against the design and Pep provider SHA. Fix every Critical/Important finding and re-review the exact diff.
- [ ] Push the exact tested head, wait for required GitHub checks, verify zero unresolved review threads, and update the draft PR with exact test/workflow evidence.
- [ ] Do not merge or mark H6 complete until the plan/design review gate has already been satisfied and all implementation gates are green.
- [ ] After a guarded merge, verify `origin/main` equals the merge result and required main workflows are green. Do not deploy, configure keys, create mappings, enable either flag, start H6S, start H7 or touch LIVE.

Checkpoint: `docs: record H6 release evidence`

## Stop and handoff

This planning PR stops before Task 1. Implementation begins only after design and plan review approval. The implementation PR must preserve every default-off and no-LIVE boundary above.

**LIVE changes: none.**
