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
  That is not the provider pin. The successful
  [provider-pin QA run 37799930021](https://github.com/PArkDevolpments/Pep-Site/actions/runs/37799930021)
  printed no image provenance. Neither establishes the required exact-pin target.
  The native Windows Docker CLI was absent during the first
  attempt, which exited 1 with `DOCKER_UNAVAILABLE`. Continuation found a local
  WSL Docker 29.1.3 engine in `Ubuntu-24.04`; the earlier absence statement did
  not cover that engine. Successful local Core probing must emit
  `build.ha_version`, `build.ha_image_tag`, `build.ha_image_digest`, and
  `build.ha_image_id`. Missing tag/digest or an installed HA version inconsistent
  with the image tag fails closed. The explicitly selected official local image
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
  This image differs from the historical Pep image above. Task 8 remains
  **PARTIAL** on original-target provenance/proof, despite this supplemental pass.
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
