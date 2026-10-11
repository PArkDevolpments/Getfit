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
  registry digest. H6 uses that same provenance, without inventing a replacement.
- Exact HA version, tag, registry digest and image ID: **pending the first
  exact-head Core-image CI artifact**. Docker is not installed in this Windows
  session. The attempted local probe exits 1 with `DOCKER_UNAVAILABLE`; it has
  established no HA compatibility evidence. Successful CI must emit
  `build.ha_version`, `build.ha_image_tag`, `build.ha_image_digest`, and
  `build.ha_image_id`. Missing tag/digest or an installed HA version inconsistent
  with the image tag fails closed.
- Task 8 workflow run URL/result: **unavailable; this commit has not been pushed**.
  The [Getfit CI workflow page](https://github.com/PArkDevolpments/Getfit/actions/workflows/ci.yml)
  is a discovery link, not evidence of a successful Task 8 run. Record the actual
  exact-head run URL and image metadata during Task 9 after independent review.

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

## Independent target Core-image gate

The `h6-core-image` CI job runs only for pushes or same-repository PRs, on
`[self-hosted, linux, x64, peptide-ha-qa]`, and requires runner `Peptide-HA-QA`.
Fork PR code is excluded from the private runner. It checks out exact Getfit
source and the pinned Pep SHA. The probe reads image identity from
`menu-ha-candidate`, then runs a separate disposable container by immutable
image ID with `--network none`, no published ports, no Docker socket or host
configuration mounts, dropped capabilities, and a read-only source mount.
The existing candidate container is only inspected; it is never mutated.

Inside that container the probe starts real HA HTTP/WebSocket infrastructure,
creates a throwaway synthetic HA user/access token, installs/imports the exact
Pep component, and invokes its production `async_get_health_authority_surfaces`
registration path. This deliberately exercises the production Health service
adapter rather than claiming full Pep integration boot. It binds Pep's real
assertion verifier, identity map and Health transport to an isolated synthetic
mapping and ephemeral public key. A synthetic clock offset allows the verifier
to be tested after its 35-second startup quarantine. Health authority remains
false, so no Health computation or data source access is permitted.

An actual HA WebSocket `call_service` command with `return_response=true` must
yield a successful HA result containing the governed `{status_code, body,
headers}` envelope. Getfit's production parser must accept its no-store
`503 HEALTH_AUTHORITY_DISABLED` denial. That denial follows valid assertion and
synthetic user resolution, proving that the registered Pep service was reached.
Missing registration, auth failure, unsupported response behavior, invalid
envelope, or failed invariants makes this mandatory job fail.

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
- Docker Core attempt: exit 1, `DOCKER_UNAVAILABLE`; no image metadata or Core
  proof was available. No staging or LIVE endpoint was contacted.
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
- PyYAML parsed `.github/workflows/ci.yml`; focused workflow assertions verified
  job names, the dedicated runner labels, same-repository fork guard, pinned Pep
  checkout and Core probe command. `git diff --check` passed. `actionlint` is
  unavailable locally; exact-head GitHub Actions semantics are still pending.

## Separate pre-LIVE L1 gate

No representative disposable deployed Supervisor + Getfit + Pep staging
topology was available during this task. L1 remains required before LIVE:
trusted Ingress subject, spoof rejection, actual app-to-Core service path,
Pep subject mapping rather than caller identity, clock skew, matching keys and
revocation/rotation, and deleted/deactivated/unmapped user isolation. Neither
the deterministic harness nor a successful Core-image artifact can close L1.
Do not substitute LIVE for missing staging. Default-off/read-only/no-LIVE/no-H6S/
no-H7 boundaries remain in force.
