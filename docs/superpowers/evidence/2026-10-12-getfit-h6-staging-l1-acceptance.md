# H6 disposable non-LIVE staging L1 acceptance runbook

**Status: NOT EXECUTED; L1 OUTSTANDING before LIVE.** This document is a procedure,
not authorization to create, access, deploy, configure or enable an environment.
An operator must obtain explicit authorization for the named disposable
non-LIVE Supervisor + Getfit + Pep environment, its synthetic fixtures/keys,
fault injection, clock tests, configuration changes and cleanup. Enabling Pep's
`server_health_authority_enabled` on staging needs explicit non-LIVE
authorization in addition to Getfit activation. Do not substitute LIVE when
staging is unavailable. No LIVE keys, identities, mappings, Health data,
publication/deployment, H6S or H7 is in this procedure's scope.

Authority: the [H6 design](../specs/2026-10-08-getfit-h6-health-context-production-binding-design.md),
[implementation plan](../plans/2026-10-08-getfit-h6-health-context-production-binding.md),
[add-on operations](../../../getfit/DOCS.md) and
[contract evidence](2026-10-08-getfit-h6-contract-evidence.md). Getfit owns workout
authority; Pep alone owns Health interpretation. The current exact f61
QA/candidate image gate remains **BLOCKED** pending authoritative provenance.
Historical 2026.9.4 and supplemental 2026.10.0 Core passes are separate evidence;
neither identifies that image or proves L1. A new staging inventory must be
identified in its own right, without an equivalence claim.

## 1. Attest the environment and freeze the inventory

Before any mutation, the operator and independent acceptance reviewer record:

1. The authorization reference, permitted staging actions, UTC window, disposable
   environment alias, operator/reviewer aliases and explicit non-LIVE
   attestation. Confirm the HA instance, Supervisor, add-on storage, Pep recorder,
   credentials, network and backup locations are dedicated to synthetic staging.
   No production mounts, real Health integrations, shared databases, production
   credentials or routes capable of writing to LIVE may be present. Record only
   attestation booleans, never addresses, secrets or private configuration.
2. The exact Getfit checkout/build SHA, pinned Pep SHA
   `f61b9644a88c5047176e87d4a7edf2939e218d32`, schema digest, HA Core and Supervisor
   versions, add-on build/version and architecture. Record registry index,
   platform manifest, config digest and actual runtime image ID for each
   container image, plus immutable source/build provenance and verified version
   consistency. Resolve tags to immutable digests before installation and
   confirm the running instances use those exact artifacts. A mutable tag or
   version string alone is insufficient. Record the authority source for the
   actual target image; unknown identity leaves the current-image gate blocked.
3. The runtime option baseline: Getfit `pep_health_enabled=false`, Pep server
   Health authority off; required `homeassistant_api: true` without additional
   Supervisor administration privilege, host networking or Docker socket.
   Record isolated staging rollback/snapshot references, not their contents.
   Save any necessary secret configuration privately in staging, never in the
   shareable evidence. Freeze the inventory; an image/code change invalidates
   results for that head and requires affected checks to be repeated.

Useful read-only inventory commands on the authorized staging host are:

```text
git rev-parse HEAD
git -C <pinned-provider-checkout> rev-parse HEAD
docker image inspect <immutable-image-ref> --format '{{.Id}} {{.Os}}/{{.Architecture}} {{json .RepoDigests}}'
docker inspect <staging-container> --format '{{.Image}}'
```

Use only these selected image fields; do not dump full container/image inspection
objects, environment variables, add-on options, headers or logs. Record Core and
Supervisor versions using their authorized administrative version display. Link
the registry/build evidence that joins index/platform/config identity; the
commands alone do not prove provenance or deployed topology.

## 2. Prepare synthetic fixtures and a private assertion checker

Create two ordinary, distinct synthetic HA users A and B and isolated Getfit
workout persons plus Pep persons/profiles. Map each HA user explicitly on both
sides using the supported staging administrative procedure. Use distinguishable
deterministic synthetic Health values and a synthetic workout programme. Seed
only the disposable staging sources/recorder supported by the pinned provider;
disable external real-data integrations. Prepare a third synthetic unmapped
user. Retain the fixture manifest privately and report only its synthetic-only
attestation and isolation pass/fail booleans.

Generate independent ephemeral Ed25519 key pairs K1 and K2 and staging-only key
aliases. Install K1's public verifier key in Pep. Configure exactly one Getfit
private seed and matching `kid` through its masked option/private-file path;
do not place raw key material in shell arguments, traces, reports or screenshots.
Check file type/permissions privately against the operations contract. A disabled
reader must not load that key. Getfit must never hold two active private keys or
automatically fall back to a second signer.

Arrange a staging-only checker that validates sensitive values **in memory** and
emits only the allowlist in section 8. It must observe the actual deployed
Ingress/signer/proxy/service boundaries without replacing them for the normal
L1 path. The checker compares assertion subject to the authenticated staging
user, verifies signature/header/claims and command shape, tracks call/socket/task
counts and checks response isolation without exporting the observed values.
Its own signed negative fixtures use only ephemeral keys, unique JTIs and the
actual staging service. Disable frame/HTTP/debug tracing; never dump assertions,
tokens, headers, raw identities, Health payloads or private logs. If a safe
observation/fault mechanism is unavailable, mark the affected row BLOCKED rather
than weakening evidence or enabling logging. Keep any fixture fault adapter
isolated to staging and identify its use separately from normal deployed proof.

## 3. Prove disabled, trusted Ingress and the actual service path

1. With both flags off, browse Getfit through the actual Supervisor Ingress as A
   and B. Confirm safe Health-unavailable presentation, zero Health key loads,
   assertions/connections/service calls, and working workout navigation. Start,
   autosave and resume separate synthetic drafts to establish continuity.
2. Under the explicit staging authorization, enable only Getfit with K1 while
   leaving Pep authority off. Restart Getfit; after Pep quarantine ends, make a
   fresh browser request. Confirm exactly one actual connection to
   `ws://supervisor/core/websocket`, private authentication using the actual
   staging `SUPERVISOR_TOKEN`, and one `peptide_site.get_health_context` command
   with `return_response=true` and `service_data` containing only `assertion`.
   No `target`, person/profile/user/source/entity selectors or fabricated Ingress
   headers may enter that command. Validate the real no-store service envelope
   and `HEALTH_AUTHORITY_DISABLED` unavailable state without printing it. The
   system/Supervisor credential must never become the asserted Health person.
3. Reject direct access outside the trusted Supervisor source with spoofed
   `X-Remote-User-Id`. Through Ingress, submit synthetic A/B identity selectors
   in query/header/form/cookie inputs and verify they cannot choose the subject
   or cause B's context to appear for A. Rejection may occur at identity/selector
   validation; observe zero unauthorized signer/service calls. Confirm missing
   trusted principal fails closed without recovering from a local mapping.
4. Only if Pep staging Health enablement is explicitly authorized, enable Pep
   authority with isolated synthetic sources. After any verifier restart's
   quarantine, request A, B, then A again through separate authenticated browser
   sessions. Privately verify the signed subject follows the trusted HA user,
   Pep resolves its own mapping, and only that user's closed v1 projection reaches
   presentation. Confirm `automatic_action=false`, `causation_asserted=false`,
   approved presentation fields only, no locally calculated Health, no fallback
   and no Health-triggered workout export/callback. Without that authorization,
   record enabled-context/isolation rows BLOCKED; a denial alone cannot pass them.

## 4. Assertion timing, replay and fresh later requests

Use the actual staging service and a private synthetic fixture checker with an
isolated UTC reference. Never change a shared or LIVE clock. Record case aliases,
pass/fail and timing bounds only. Keep each case's JTI unique except the deliberate
replay pair. Test verifier timing after its startup quarantine so it cannot mask
assertion rejection. Select times with adequate margin for network scheduling;
an ambiguous boundary measurement is inconclusive and must be repeated safely.

- Verify Getfit's normal assertion has `exp - iat = 30` seconds, issuer `getfit`,
  audience `peptide-health-read`, `typ=H0-SA`, EdDSA, matching header/claim `kid`
  and a new JTI per later browser request. Reject zero/negative and greater-than-
  30-second lifetimes, invalid signature/issuer/audience/type/kid and replay.
- Verify Pep's five-second skew rule with signed synthetic service fixtures:
  future issuance within five seconds and expiration within the five-second
  grace window are admissible; issuance more than five seconds ahead and
  expiration more than five seconds behind are `INVALID_SERVICE_ASSERTION`.
  Test both sides of each bound with scheduling margin, validate expected
  preconditions privately, and do not call nominal boundary jitter a pass.
- Restart/reload Pep's actual verifier in staging and measure monotonic uptime.
  Fresh requests strictly within its first 35 seconds must finish unavailable
  as `SERVICE_ASSERTION_STARTUP_QUARANTINE`, within Getfit's normal five-second
  operation budget rather than waiting for quarantine. After at least 35 seconds,
  make a **new** request with a fresh assertion and verify ordinary acceptance.
  Account for startup readiness separately; use an external test schedule, never
  a held/retried Getfit request. `Retry-After` is discarded without parsing or
  retention. Also check oversized/negative/non-numeric metadata in the isolated
  fault path; none may delay, trigger another call or escape into evidence/UI.

The post-quarantine, post-recovery or post-rotation request is a separate later
request. It does not prove or permit an in-request retry. Each eligible read
has at most one connection and one service command; failures before connection
or command can have zero. Disabled/identity-rejected reads have zero attempts.

## 5. Sequential rotation, revocation and changing users

1. With K1 working, add K2's public verifier key to Pep while retaining K1, apply
   the supported reload and observe the 35-second quarantine using fresh
   requests. After quarantine, confirm the K1 Getfit configuration still works.
2. Replace Getfit's one active private seed/`kid` with K2 and restart Getfit.
   Privately prove new requests use only K2 and remain isolated for A/B while
   Pep accepts the public-key overlap. No alternate-key retry is allowed.
3. Remove K1's public key from Pep, reload, and observe quarantine. Afterward,
   verify K2 success and rejection of a fresh K1-signed synthetic fixture at the
   actual service. To verify the Getfit denial path, separately switch its single
   staging signer back to K1 and restart: new reads must fail unavailable without
   trying K2. Restore K2 as a separate configuration/restart; no simultaneous
   private keys. Record booleans only, without actual key bytes or assertions.
4. Exercise emergency revocation by removing the active public key in Pep,
   disabling Getfit Health and reloading Pep. Disabled Getfit issues no assertion
   or call; after quarantine, the private service fixture using the revoked key
   is rejected. Workouts remain usable. Re-enable/reinstall only when explicitly
   included in the staging authorization; otherwise retain the safe off state.
5. Restore a valid staging key configuration for user-lifecycle cases, then in
   separate cases deactivate, delete and remove Pep mapping for a synthetic user.
   New service fixtures for the unavailable subject must yield
   `PERSON_CONTEXT_UNAVAILABLE`; browser access may be rejected earlier by HA.
   Report those layers separately rather than expecting a deleted user to log in.
   No prior success or another user's values may appear. Test an ambiguous mapping
   as fail-closed using the supported isolated fixture procedure.
6. Remap synthetic A to a different Pep person/profile, leaving Getfit's expected
   mapping unchanged. A subsequent fresh read must reject a mismatching person/
   profile and show unavailable, with no old/cross-person context. Then align the
   authorized staging Getfit mapping and repeat a fresh request: only the newly
   mapped person's synthetic context may appear. Return A/B fixtures to the
   declared baseline or record their disposal for cleanup. Do not edit real users.

## 6. Failure matrix and workout continuity

First obtain a valid synthetic A projection, then run each failure on a fresh B
request, followed by a separate recovered B request where recovery is authorized.
Use actual staging flags, restart, auth and identity changes for those cases.
Inject protocol/provider/deadline faults only at a declared disposable staging
boundary, restore it between cases, and record which rows use a fixture. A
synthetic replacement for the proxy/service cannot pass the normal deployed path
row. Treat an unexercised failure as NOT RUN, not as covered by a prior unit test.

| Case | Required result for the current request |
| --- | --- |
| Getfit off | `GETFIT_PEP_HEALTH_DISABLED`; zero signing/transport attempts. |
| Invalid key/missing token configuration | `PEP_HEALTH_CONFIGURATION_INVALID`; workouts still served. |
| Pep authority off | `HEALTH_AUTHORITY_DISABLED`; no retry or retained projection. |
| Actual verifier startup | `SERVICE_ASSERTION_STARTUP_QUARANTINE`; no quarantine sleep. |
| Invalid/removed key, invalid claims or replay | `INVALID_SERVICE_ASSERTION`; no alternate-key attempt. |
| Deleted/deactivated/unmapped/ambiguous user | Identity denial or `PERSON_CONTEXT_UNAVAILABLE` at the applicable layer; never another person. |
| Remapped person/profile mismatch | Unavailable; stable mismatch reason privately checked, no partial/old values. |
| Rate limiting | `ASSERTION_RATE_LIMITED`; no automatic retry or retained Retry-After. |
| Provider rebuild timeout, overload, compute/integrity failure | `PEP_HEALTH_UNAVAILABLE` for non-allowlisted provider errors; no raw provider message. |
| Socket refusal, failed proxy authentication, malformed frame/result ID/envelope/no-store, invalid closed schema/type/authority/action flags | Safe unavailable; no direct HTTP or local Health fallback. |
| Stalled operation/close and request cancellation | Five-second operation deadline/cleanup within measured scheduling tolerance; cancellation propagates after cleanup; no surviving task/socket/timer. |

For every case privately check no A values/identities retained in B HTML, reader
state, later requests or private diagnostic channels; no assertion/token/key/
payload leakage; at most one attempted service command; closed connections and
no background retry/Health worker. Publish only absence booleans. Do not upload
private logs to demonstrate absence. Unknown provider errors remain generic;
only the reader's existing allowlisted status/reason pairs are preserved.

While Health is unavailable, perform and verify the synthetic workout sequence
for each user: start draft, autosave, leave/resume, complete Revision 1, repeat
completion idempotently, append a correction/supersession and view effective
history. Privately compare event/revision identities and draft ownership;
publish only continuity, immutable-history, idempotency and isolation booleans.
Health must not change targets, performed evidence, programme position or export
authority. Verify ordinary recovery never exposes A's prior context to B.

## 7. Rollback and cleanup

Disable Getfit Health and restart; verify zero subsequent key loads, assertions
and calls. Disable Pep's independent staging authority and restore its declared
baseline/reload procedure. Verify workout drafts, immutable completion/correction
history and navigation still work; rollback must not rewrite workout evidence.
Remove the temporary observer/fault adapter and verify ordinary off-state
behavior with no residual connector substitution, socket, task or retry timer.

Using the pre-attested resource manifest and exact staging targets, revoke and
remove ephemeral verifier keys, private seeds/files and staging-only credentials,
then remove only this run's disposable containers, synthetic users/mappings,
fixture sources/recorder volumes and private test outputs, or destroy the entire
explicitly authorized disposable environment. Do not delete shared/owner
resources, repository scratch/history, production data or broad paths. Check
remaining resource inventory against the baseline; report cleanup/credential-
revocation booleans. If disposal is not authorized, retain the environment off,
restrict access and mark cleanup pending for its owner. Keep the sanitized
acceptance record; failure must retain safe off state and gate status FAIL/BLOCKED.

## 8. Sanitized evidence and acceptance decision

Allowlist: authorization/environment aliases and non-LIVE/synthetic attestations;
UTC dates; source SHAs/schema hashes, versions, architectures and immutable image
index/platform/config IDs; public workflow/build provenance links; case aliases;
PASS/FAIL/BLOCKED/NOT RUN, stable reason/failure class, aggregate call/resource
counts, elapsed-time bounds and invariant booleans; reviewer/cleanup status.
Use fixed A/B/K1/K2 aliases, never raw identities or actual JTIs. Exclude tokens,
headers, assertions/signatures, key bytes, addresses/endpoints beyond the public
contract path, raw mappings/person/profile IDs, Health payloads/metrics, browser
storage, private configuration/logs, screenshots containing those values and
exception/frame text. An assertion checker may decode/compare privately in
memory, but its output must be allowlisted before retention or publication.

An independent reviewer records each row for the frozen inventory:

| Acceptance row | PASS requires | Initial status |
| --- | --- | --- |
| Environment and build identity | Explicit non-LIVE authorization/attestation and complete immutable running inventory. | NOT RUN |
| Default off and minimum permission | Zero Health work while disabled; no extra privileges. | NOT RUN |
| Trusted Ingress and browser spoof rejection | Subject from actual trusted principal; direct/browser selectors cannot choose identity. | NOT RUN |
| Deployed Supervisor/token/selector-free service | Actual proxy authentication/command and registered Pep envelope; no substituted normal path. | NOT RUN |
| Pep mapping and person isolation | Enabled synthetic A/B success, missing/mismatched identity rejection, no prior/cross-person state. | NOT RUN |
| Timing, replay, key lifecycle | 30s lifetime, 5s skew, 35s actual quarantine, fresh later requests, sequential single-key rotation/Pep overlap/revocation. | NOT RUN |
| User lifecycle | Deleted/deactivated/unmapped/ambiguous/remapped cases verified at their applicable layers. | NOT RUN |
| Failure, privacy and resources | Every matrix row exercised and fail-closed; no retry/sleep/leak or surviving resource. | NOT RUN |
| Workout continuity and rollback | Draft/completion/correction/isolation invariants pass during failures and off-state rollback. | NOT RUN |
| Cleanup and independent acceptance | Ephemeral credentials revoked and authorized resources disposed; sanitized record independently reviewed. Pending cleanup keeps this row BLOCKED. | NOT RUN |
| Exact f61 QA/current candidate image gate | Separate authoritative image identity and required compatibility proof; historical/supplemental images cannot substitute. | BLOCKED |

Any failed invariant yields FAIL and safe rollback. Missing authorization,
inventory, observation, case or environment yields BLOCKED/NOT RUN, never PASS.
L1 passes only when all L1 rows have actual evidence for the same frozen inventory
and independent acceptance; the separate current-image gate stays blocked until
its own provenance/compatibility requirements are satisfied. No acceptance result
here closes exact-head hosted CI, main CI, release or production-artifact gates.
The current release workflow publishes production architecture images and
version/latest manifests after successful push CI on main, so merge remains
blocked without the required publication authority; do not mutate/disable it.

Until executed and reviewed, this file remains a runbook with no environment,
test result, image-equivalence claim or LIVE authorization attached.
