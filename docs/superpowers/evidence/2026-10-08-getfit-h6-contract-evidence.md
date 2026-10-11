# H6 HA WebSocket compatibility evidence

Recorded locally on 2026-10-11. H6 remains read-only and disabled by default.
No LIVE deployment, activation, mapping, Health read, H6S or H7 work occurred.
Synthetic fixtures and ephemeral keys are confined to QA infrastructure.

## Source and image provenance

- Getfit implementation base: `908b26e33a4e6337b441e5a9b86db618e7369dda`.
  Each CI artifact records the exact Getfit checkout SHA under `build.getfit_sha`.
- Pep provider: `f61b9644a88c5047176e87d4a7edf2939e218d32`, repository
  [PArkDevolpments/Pep-Site](https://github.com/PArkDevolpments/Pep-Site).
  Docker probe installation uses `git archive` at that commit, restricted to
  `custom_components/peptide_site`; a mutable working tree is never installed.
- Pep's current target-image reference is its `.github/workflows/qa.yml` step
  `Verify Health production APIs in target Home Assistant image`, together with
  `.github/workflows/ha-runtime-qa.yml` and `PEPTIDE_HA_SHARED_RUNNER.md`.
  These derive the immutable image ID from the existing `menu-ha-candidate`
  container on the `Peptide-HA-QA` Linux runner. They commit no image tag or
  registry digest. H6 retains that provenance requirement; the supplemental
  local target below does not replace it.
- Original exact-provider Pep candidate HA version, tag, registry digest and
  image ID: **unreconciled**. Historical
  [Pep runtime run 37628786842](https://github.com/PArkDevolpments/Pep-Site/actions/runs/37628786842)
  at `cb3de069d418d0651eb74c54b31a92da079c8066` recorded
  `sha256:3e6710a7ab2a61311d9d899b719f6c3657791c63e8f4942cec4ebc42401d6b76`.
  This is the last recorded Pep HA runtime verification target, not evidence of
  the currently deployed candidate or of the provider-pin QA image. The successful
  [provider-pin QA run 37799930021](https://github.com/PArkDevolpments/Pep-Site/actions/runs/37799930021)
  printed no image provenance. Exact f61 QA image identity remains unknown.
  The native Windows Docker CLI was absent during the first
  attempt, which exited 1 with `DOCKER_UNAVAILABLE`. Continuation found a local
  WSL Docker 29.1.3 engine in `Ubuntu-24.04`; the earlier absence statement did
  not cover that engine. Successful local Core probing must emit
  `build.ha_version`, `build.ha_image_digest`, and `build.ha_image_id`, together
  with a genuine `build.ha_image_tag` when available. Missing verified digest or
  an installed HA version inconsistent with a present image tag fails closed.
  The explicitly selected official local image
  `ghcr.io/home-assistant/home-assistant:2026.10.0` is a supplemental compatibility
  target, not evidence of Pep's unidentified exact-provider candidate.
- Supplemental local Core execution: **PASS**, actual HA runtime `2026.10.0`,
  linux/amd64, WSL Docker 29.1.3. Verified official registry bytes link the index,
  platform manifest and config; all 22 imported RootFS diff IDs match the config.
  Docker's actual image ID, descriptor and RepoDigest use the platform manifest
  digest, not the config digest on this containerd engine:
  - image tag: `ghcr.io/home-assistant/home-assistant:2026.10.0`;
  - image ID/platform manifest: `sha256:956a5d9effc091888cd34cb0b6fb4f66c448d257d20519e72302557682734fd0`;
  - registry index: `sha256:1b64d38f38d922bf9d59336451fd6453e1d614f934456af4ee3d2a51061be3a4`;
  - config: `sha256:e5ee66f11f90f86c50c1b7641e558b707ccc3d2bb354daf05c296e58382945e2`.
  This image differs from the historical Pep image above and is supplemental.
- Recorded Pep runtime target Core execution: **PASS** after independently
  locating the exact historical `3e6710...` image ID as the official registry
  index. Official `2026.9.4` tag resolves to that same index; real HA runtime is
  `2026.9.4`. The pinned f61 Pep service passes all seven Core invariants in this
  isolated image. Registry index -> linux/amd64 manifest -> config hashes and all
  RootFS diff IDs are verified:
  - immutable source/image ID/index: `ghcr.io/home-assistant/home-assistant@sha256:3e6710a7ab2a61311d9d899b719f6c3657791c63e8f4942cec4ebc42401d6b76`;
  - genuine tag: `ghcr.io/home-assistant/home-assistant:2026.9.4`;
  - platform manifest: `sha256:e47c978e1b801466e7f62f612fd552bc3a228e077b31a3f1c22c05cf63d754da`;
  - config: `sha256:cd74b0e02cee84de9f53b0f8fc079c8979796b81a6b02e1ee0cd09f038703afd`.
  This is concrete compatibility evidence against the recorded Pep runtime
  target, not an assertion that f61 QA used it. Local Task 8 acceptance remains
  subject to independent scoped review; remote exact-head CI and L1 remain open.
- Task 8 workflow run URL/result: **unavailable; this commit has not been pushed**.
  The [Getfit CI workflow page](https://github.com/PArkDevolpments/Getfit/actions/workflows/ci.yml)
  is a discovery link, not evidence of a successful Task 8 run. Record the actual
  exact-head hosted-CI run URL during Task 9 after independent review. No private
  Core-image job is scheduled in Getfit Actions: Getfit has no repository runners;
  Pep's runner is repository-scoped/offline and the default Getfit token cannot
  check out the private Pep repository. Local Core proof is a separate operation.

## Deterministic Supervisor boundary evidence

`--proxy-harness` uses Getfit's real `build_pep_health_reader`, private-key loader,
Ed25519 signer, `HaHealthServiceClient`, and fail-closed reader. Only the connector
routing is substituted to an ephemeral loopback WebSocket peer. The connector
verifies that Getfit selected exactly `ws://supervisor/core/websocket` before
routing locally. The peer checks authentication against the synthetic value
supplied through `SUPERVISOR_TOKEN`, the exact assertion-only `call_service`
command, `return_response=true`, the signature and governed assertion claims.
The real reader parses a governed no-store authority-disabled envelope, and the
connection closes. All seven invariant booleans passed locally.

The harness is protocol/proxy contract proof, not a deployed Supervisor appliance.
Its response is synthetic. It does not establish an HA image's service support.
The ordinary hosted `quality` CI job runs its tests and preserves only the
allowlisted `h6-proxy-contract` JSON artifact.

Existing H0 findings remain applicable as architecture provenance:
[H0 transport decision at the pinned provider commit](https://github.com/PArkDevolpments/Pep-Site/blob/f61b9644a88c5047176e87d4a7edf2939e218d32/docs/superpowers/evidence/2026-10-01-health-authority-h0-decision.md).
H0 inspected Supervisor source `92e68f476e7db7ad14c2fd362ef9489328e87091`
and explicitly used a composite representative identity-path proof. It recorded
Getfit CI run `36826752890` for its historical Getfit SHA; that is historical H0
provenance, not a current H6 verification result. H0 did not claim its Core-only
stage was a full Supervisor stage, and this task preserves that limitation.

## Independent local Core-image probe

Getfit's workflow retains only the deterministic hosted proxy gate and its
sanitized artifact. The local Core probe can inspect an explicitly selected
official image using `--image-ref`, with `--wsl-distro Ubuntu-24.04` for the local
Windows/WSL engine. Without an explicit reference it retains the historical
read-only `menu-ha-candidate` lookup, which is unavailable in this session.
It archives the local provider git object at the pinned SHA, then runs a separate
disposable container by immutable
image ID with `--network none`, no published ports, no Docker socket or host
configuration mounts, dropped capabilities, and a read-only source mount.
No existing container is mutated. The probe never pulls an image or changes
Docker/WSL configuration. Image acquisition and provenance must be established
separately before execution.

Inside that container the probe starts real HA HTTP/WebSocket infrastructure,
creates a throwaway synthetic HA user/access token, installs/imports the exact
Pep component, and invokes its production `async_get_health_authority_surfaces`
registration path. This deliberately exercises the production Health service
adapter rather than claiming full Pep integration boot. It binds Pep's real
assertion verifier, identity map and Health transport to an isolated synthetic
mapping and ephemeral public key. A synthetic clock offset allows the verifier
to be tested after its 35-second startup quarantine. Health authority remains
false, so no Health computation or data source access is permitted.

The corrected worker initializes HA's loader, ConfigEntries and base registries
before component setup, then processes the isolated auth configuration. A normal
synthetic user refresh token supplies the required synthetic loopback client ID.
These use actual Core APIs, not bootstrap stubs. References:
[Core bootstrap](https://github.com/home-assistant/core/blob/2026.10.0/homeassistant/bootstrap.py),
[Core config](https://github.com/home-assistant/core/blob/2026.10.0/homeassistant/core_config.py),
[Core auth](https://github.com/home-assistant/core/blob/2026.10.0/homeassistant/auth/__init__.py).

An actual HA WebSocket `call_service` command with `return_response=true` must
yield a successful HA result containing the governed `{status_code, body,
headers}` envelope. Getfit's production parser must accept its no-store
`503 HEALTH_AUTHORITY_DISABLED` denial. That denial follows valid assertion and
synthetic user resolution, proving that the registered Pep service was reached.
Missing registration, auth failure, unsupported response behavior, invalid
envelope, or failed invariants makes the local command fail.

Only build identity, proof classification, pass/fail, stable failure class, and
boolean invariants can escape the probe. Captured subprocess/HA diagnostics are
discarded, never uploaded. No assertion, key, token, subject, person/profile ID,
Health body or raw frame is included in artifacts. Core-image proof does not
prove `ws://supervisor/core/websocket`, Supervisor token flow, full Pep startup,
or a deployed Getfit/Pep topology.

## Local commands and observed results

```powershell
uv run pytest _tools/tests/test_qa_h6_ha_websocket_contract.py -q --basetemp=.pytest-h6-task8
uv run python _tools/qa_h6_ha_websocket_contract.py --help
uv run python _tools/qa_h6_ha_websocket_contract.py --proxy-harness
uv run python _tools/qa_h6_ha_websocket_contract.py --docker-core --provider-repo ../Pep-Site-H5
uv run ruff check _tools/qa_h6_ha_websocket_contract.py _tools/tests/test_qa_h6_ha_websocket_contract.py
uv run mypy src
uv run pytest -q --basetemp=.pytest-h6-task8-full
uv run pytest -q --import-mode=importlib --basetemp=.pytest-h6-task8-full-importlib
git diff --check
```

- TDD: initial 11 focused failures observed because the gate was missing. A later
  negative provenance test failed when mismatched installed HA version/tag was
  accepted; version/tag matching was added and the focused suite passed.
- Focused tool tests: 14 passed, covering real loopback protocol behavior,
  incorrect endpoint, rejected auth, missing no-store, output allowlist,
  unavailable Docker, missing digest, unsafe worker output and version mismatch.
- Help: exit 0. Proxy harness: exit 0, all seven invariants true.
- Original native Windows Docker Core attempt: exit 1, `DOCKER_UNAVAILABLE`.
  The first WSL-backed attempt returned `IMAGE_PROVENANCE_UNAVAILABLE` before
  acquisition. These are historical diagnostics, not the current engine state.
- Ruff: passed. Project strict mypy: passed, 75 source files. The project mypy
  scope is `src`/package `hwa`; the standalone QA tool/tests are outside it.
- Bare full pytest: collection failed on duplicate module names
  `tests/unit/read_models/test_progress.py` and
  `tests/unit/services/test_production_bootstrap.py`, colliding respectively
  with `tests/integration/web/test_progress.py` and
  `tests/integration/test_production_bootstrap.py`. No task-scope code was changed
  to alter that existing layout.
- Full suite with importlib collection: 846 passed, 6 Windows/POSIX boundary
  skips, and one existing Starlette/httpx deprecation warning.
- PyYAML parsed the original workflow; original shape assertions passed but
  could not establish private runner scheduling or cross-repository access.
  Independent review found those infrastructure assumptions invalid. The
  continuation removes that Core job and private checkout and validates the
  remaining hosted proxy gate. `actionlint` is unavailable locally; exact-head
  GitHub Actions semantics remain pending.

Continuation used the existing `.venv` directly without changing the preserved
untracked `uv.lock` (SHA-256
`145296C31A9FCFA20D9BB548112E821C060EF7822892CACDEBF8D8E710A97A82`):

```powershell
$env:H6_CORE_REGRESSION='1'
.venv/Scripts/python.exe -m pytest _tools/tests/test_qa_h6_ha_websocket_contract.py -q --basetemp=.pytest-h6-t8final
Remove-Item Env:\H6_CORE_REGRESSION
.venv/Scripts/python.exe _tools/qa_h6_ha_websocket_contract.py --docker-core --image-ref ghcr.io/home-assistant/home-assistant:2026.10.0 --wsl-distro Ubuntu-24.04 --provider-repo ../Pep-Site-H5 --image-provenance .superpowers/sdd/2026-10-08-getfit-h6-health-context-production-binding/image-acquisition/oci-verified-2/provenance.json
.venv/Scripts/python.exe _tools/qa_h6_ha_websocket_contract.py --docker-core --image-ref ghcr.io/home-assistant/home-assistant@sha256:3e6710a7ab2a61311d9d899b719f6c3657791c63e8f4942cec4ebc42401d6b76 --wsl-distro Ubuntu-24.04 --provider-repo ../Pep-Site-H5 --image-provenance .superpowers/sdd/2026-10-08-getfit-h6-health-context-production-binding/image-acquisition/target-lookup/acquired/provenance.json
.venv/Scripts/python.exe _tools/qa_h6_ha_websocket_contract.py --proxy-harness
.venv/Scripts/python.exe -m ruff check _tools
.venv/Scripts/python.exe -m mypy src
```

- Actual RED: the preserved original `5f68a53` worker failed on this real image
  before service proof (`UNSAFE_REPORT`, all Core invariants false). A separate
  narrow diagnostic reported only `RuntimeError`; no raw exception or identity
  was retained. Bootstrap prerequisites were missing in the original source.
- Actual GREEN: corrected worker on the same supplemental image, exit 0,
  `failure_class=NONE`, all seven Core invariants true. HA WebSocket dispatch
  returned the registered pinned Pep service's governed no-store denial.
- Recorded historical target GREEN: same isolated production service probe on
  immutable `3e6710...` index / actual HA `2026.9.4`, exit 0, NONE and all seven
  Core invariants true. No provider code changed. This is not Supervisor proof.
- Immutable index support: three new cases RED then GREEN (valid index ID/ref,
  wrong source digest rejection, tagless verified-ref behavior). Subsequent
  scoped suite: **21 passed, 1 opt-in real-image skip in 1.44s**. Digest mode
  retains the verified immutable index/platform/config links; if no genuine tag
  exists it omits `ha_image_tag` rather than manufacturing one. Where tags exist,
  their version must still match the real HA runtime. Both actual local image
  executions succeeded independently of that hosted-suite opt-in skip.
- Four registry-document provenance cases added; initial missing-function RED,
  then GREEN. Final focused suite, including the opt-in real-image regression:
  **19 passed in 10.27s**. The real-image test remains opt-in locally; hosted CI
  skips it and exercises the synthetic proxy gate independently.
- Continuation help exit 0, proxy exit 0/all seven true, Ruff passed, strict
  project mypy passed (75 files), PyYAML/hosted-only workflow assertions passed,
  and `git diff --check` passed. No full-suite repeat was needed after the scoped
  fixes; the earlier 846-pass importlib result remains historical.
- Published implementation-base CI is not uniformly green:
  [push run 38140165753](https://github.com/PArkDevolpments/Getfit/actions/runs/38140165753)
  failed an initial READY test assertion, while
  [PR run 38140169015](https://github.com/PArkDevolpments/Getfit/actions/runs/38140169015)
  passed on the same `908b26e` head. A 30ms synthetic deadline is a suspected
  cause, not a verified diagnosis or fix. No unrelated test was changed.

## Separate pre-LIVE L1 gate

No representative disposable deployed Supervisor + Getfit + Pep staging
topology was available during this task. L1 remains required before LIVE:
trusted Ingress subject, spoof rejection, actual app-to-Core service path,
Pep subject mapping rather than caller identity, clock skew, matching keys and
revocation/rotation, and deleted/deactivated/unmapped user isolation. Neither
the deterministic harness nor a successful Core-image artifact can close L1.
Do not substitute LIVE for missing staging. Default-off/read-only/no-LIVE/no-H6S/
no-H7 boundaries remain in force.

## Task 9 local continuation — 2026-10-11

Prospective independent plan approval and scoped local Task 8 acceptance are now
recorded in the ignored continuation workspace. Task 8 acceptance applies to
`58708599a8800b20fdc5caeee442e5efcb2128c8`; it does not backdate approval of the
earlier implementation or close remote CI, exact-provider QA/current candidate
image identity or representative staging L1. This continuation permits local
documentation, verification and a separate commit only. No push, PR change,
merge, version bump, release, LIVE access/activation, H6S or H7 occurred.

README and the new `getfit/DOCS.md` document default-off/read-only behavior,
stable unavailable states, private-file signing, minimum HA Core API permission,
one active Getfit key, Pep public-key overlap, rotation/revocation and rollback.

### Published CI failure investigation and test-only RED/GREEN

The shared `HealthHarness` used a 30ms deadline for ordinary success setup, even
though production uses five seconds. A controlled 50ms scheduling delay in its
synthetic peer exercised the real signer, client and reader and reproduced the
initial READY failure: the default case returned UNAVAILABLE. A separate case
with an explicit 30ms deadline correctly returned UNAVAILABLE. This establishes
the harness timing mechanism; the old remote run contains no elapsed-time trace
that could retrospectively prove its exact scheduler delay.

Only the shared test harness default changes to one second. The new delayed-peer
regression keeps explicit 30ms deadline exhaustion, closed connections, no
surviving tasks and private-log assertions. Existing timeout, cancellation,
retry-metadata, person-isolation and recursive retained-state assertions remain.
The e2e tests import this harness and require no assertion changes. Production
code, its five-second deadline and Health behavior are unchanged.

```powershell
.venv/Scripts/python.exe -m pytest tests/integration/test_h6_health_failure_matrix.py -q -k scheduling_delay --basetemp=.superpowers/sdd/2026-10-08-getfit-h6-health-context-production-binding/task9-red
.venv/Scripts/python.exe -m pytest tests/integration/test_h6_health_failure_matrix.py tests/e2e/test_h6_health_privacy_and_isolation.py -q --basetemp=.superpowers/sdd/2026-10-08-getfit-h6-health-context-production-binding/task9-green
```

RED: 1 failed (delayed ordinary READY setup), 1 passed, 45 deselected.
GREEN: 70 passed, one existing Starlette/httpx deprecation warning.

### Fresh local verification

The original untracked `uv.lock` remains byte-identical, SHA-256
`145296C31A9FCFA20D9BB548112E821C060EF7822892CACDEBF8D8E710A97A82`.
Adapted sync asserts an unchanged lock and retains the existing Windows tzdata
prerequisite/extraneous packages. Subsequent commands use `--no-sync` so they
cannot rewrite the lock or remove that prerequisite. All basetemps below were
new, inside the ignored continuation workspace. Prior artifacts are preserved.

```powershell
uv sync --dev --locked --inexact
uv run --no-sync ruff check .
uv run --no-sync mypy src
uv run --no-sync pytest tests/unit -q --basetemp=.superpowers/sdd/2026-10-08-getfit-h6-health-context-production-binding/task9-unit
uv run --no-sync pytest tests/integration -q --basetemp=.superpowers/sdd/2026-10-08-getfit-h6-health-context-production-binding/task9-integration
uv run --no-sync pytest tests/contract -q --basetemp=.superpowers/sdd/2026-10-08-getfit-h6-health-context-production-binding/task9-contract
uv run --no-sync pytest tests/e2e -q --basetemp=.superpowers/sdd/2026-10-08-getfit-h6-health-context-production-binding/task9-e2e
uv run --no-sync pytest tests/unit/integrations/pep tests/integration/test_h6_health_failure_matrix.py tests/integration/web/test_h6_health_identity.py tests/contract/test_h6_health_service_contract.py tests/e2e/test_h6_health_privacy_and_isolation.py _tools/tests/test_qa_h6_ha_websocket_contract.py -q --import-mode=importlib --basetemp=.superpowers/sdd/2026-10-08-getfit-h6-health-context-production-binding/task9-focused
uv run --no-sync pytest -q --basetemp=.superpowers/sdd/2026-10-08-getfit-h6-health-context-production-binding/task9-bare
uv run --no-sync pytest -q --import-mode=importlib --basetemp=.superpowers/sdd/2026-10-08-getfit-h6-health-context-production-binding/task9-full-importlib
uv run --no-sync python _tools/qa_h6_ha_websocket_contract.py --proxy-harness
uv run --no-sync python .superpowers/sdd/2026-10-08-getfit-h6-health-context-production-binding/verify-task9-migrations.py
git diff --check
```

- Sync: exit 0, 47 packages resolved / 46 checked. Ruff: all checks passed.
  Strict mypy: no issues in 75 source files.
- Split CI suites: unit 231 passed / 6 skipped; integration 169 passed;
  contract 327 passed; e2e 121 passed. Total: **848 passed, 6 skipped**.
- Focused H6/transport/tool suite: **277 passed, 7 skipped**. Six skips concern
  Windows symlink privilege and POSIX key-file boundaries; the seventh is the
  opt-in real-image tool test. Actual Task 8 Core runs remain separate evidence.
- Bare pytest: exit 1 at collection, the two previously recorded duplicate-module
  errors (`test_progress.py`, `test_production_bootstrap.py`). No layout change or
  deletion of preserved caches was made. Importlib full suite: **848 passed,
  6 skipped**. Each suite emits the existing Starlette/httpx warning.
- Fresh deterministic proxy CLI: exit 0, NONE, all seven invariants true. It
  records base SHA 5870859 while documentation/test changes are uncommitted;
  it is not exact-head remote CI or representative deployed Supervisor evidence.
- Safe migration adaptation: Alembic Config API overrides only sqlalchemy.url
  to a new scratch SQLite database. `upgrade head` succeeds twice, actual head
  equals `0003`, 13 tables. Scratch retained under
  `task9-migrations-eqz1ld0c/scratch.sqlite3`. No owner `hwa.db` exists in this
  checkout; no owner database was opened, removed or overwritten.

### Local Docker build, with recorded environment adaptations

Controller acquisition verified official public Dockerfile base
`ghcr.io/home-assistant/base-python:3.12-alpine3.24`, original index
`sha256:528aa9bc123dfd10a95210691973d2c507c579157a1af33aac28cbd9672a002d`,
linux/amd64 manifest
`sha256:227b19ebc05c44219baf06f8eef2cfb200b3864a27de2772cc50e7e2e68fcadc`
and config `sha256:741c53d86f2fa1d5117c365becd524fe8d9114e2990e9b5fc79895715fb4dfd2`.
Verified source bytes, archive/blob hashes, actual Docker identity and all three
RootFS diff IDs are retained under ignored `image-acquisition/getfit-build-base`.
Only the amd64 descendants were acquired; no signature verification is claimed.

The ordinary repository-context build was interrupted before any build steps
because it was transferring the approximately 2.94GB preserved ignored workspace.
A new ignored `task9-build-context` copies the exact Dockerfile and all its COPY
inputs plus `.dockerignore`. SHA-256 comparisons of 147 inputs passed. Its plain
build reached pip build-dependency installation but made no progress through the
known WSL DNS limitation; that task-owned build client was interrupted. Neither
interruption is a successful normal build or a completed pip-error diagnostic.

Windows DNS freshly resolved the package index hosts. The successful adaptation
uses only ephemeral build-container host mappings and retains HTTPS/TLS domain
validation and the base image's existing package indexes:

```powershell
wsl -d Ubuntu-24.04 --cd /mnt/c/Users/myher/Documents/Codex/2026-10-05/continue-work-in-ktgregson93-collab-pep/work/Getfit-H6 -- docker build -t getfit-h6-ci .
wsl -d Ubuntu-24.04 --cd /mnt/c/Users/myher/Documents/Codex/2026-10-05/continue-work-in-ktgregson93-collab-pep/work/Getfit-H6/.superpowers/sdd/2026-10-08-getfit-h6-health-context-production-binding/task9-build-context -- docker build -t getfit-h6-ci .
wsl -d Ubuntu-24.04 --cd /mnt/c/Users/myher/Documents/Codex/2026-10-05/continue-work-in-ktgregson93-collab-pep/work/Getfit-H6/.superpowers/sdd/2026-10-08-getfit-h6-health-context-production-binding/task9-build-context -- docker build --add-host pypi.org:151.101.0.223 --add-host files.pythonhosted.org:151.101.0.223 --add-host wheels.home-assistant.io:104.26.4.238 -t getfit-h6-ci .
wsl -d Ubuntu-24.04 -- docker image inspect getfit-h6-ci --format '{{.Id}} {{.Os}}/{{.Architecture}}'
wsl -d Ubuntu-24.04 -- docker ps -a --format '{{.ID}} {{.Image}} {{.Status}}'
```

Adapted build: **exit 0**, all 13 Dockerfile steps, tagged `getfit-h6-ci:latest`,
image `sha256:b54871f102f64cac47b8c99db13984170d87451bd2d3d6ce6934eecc59ddacc5`,
linux/amd64. Final container inventory is empty. Docker emits a legacy-builder
deprecation and pip its root-user warning. No system DNS, daemon/global config,
Dockerfile, package source or TLS trust setting changed. The Dockerfile installs
from its declared dependency ranges, not the preserved Windows lock: this proves
the local amd64 build, not locked runtime parity, aarch64 or deployed acceptance.

### Gates still open

Local Task 9 verification is ready for controller-dispatched whole-branch review;
it is not self-approved. Remote exact-head CI remains unavailable because the
local checkpoint is unpublished. Historical push/PR evidence remains mixed and
cannot be retroactively marked green by the local harness fix. Exact f61 QA/current
Pep candidate identity, representative deployed staging L1, publication, merge,
main CI, release and supported-architecture production artifact verification
remain unclosed or excluded. Do not claim H6 complete. The separate local commit
and preservation checks are recorded in ignored `task-9-report.md` for handoff.
