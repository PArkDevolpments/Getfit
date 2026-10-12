# Getfit add-on operations: optional Pep Health context

Getfit owns workouts; Pep alone owns Health interpretation. Health context is
optional, read-only and presentation-only. Getfit neither calculates readiness,
BMI, trends or recommendations nor substitutes local or another person's values.
Every accepted Pep response must keep `automatic_action=false` and
`causation_asserted=false`. Health failure leaves workout authority, draft
durability, completion, corrections and history available.

## Default-off configuration and minimum permission

`pep_health_enabled` defaults to `false`. Disabled Getfit does not load the
signing key, create an assertion or open a Health connection. Pep's independent
`server_health_authority_enabled` flag also needs separate governance; turning on
Getfit does not turn on Pep. There is no legacy HTTP Health fallback.

The add-on manifest grants `homeassistant_api: true` for the Core WebSocket
service path. H6 adds no Supervisor administration permission, host networking,
Docker socket, user-selected endpoint or browser credential. The internal
transport selects `ws://supervisor/core/websocket`, consumes the Supervisor
credential privately when constructing an enabled reader, and requests only
`peptide_site.get_health_context` with `service_data={assertion}` and
`return_response=true`. Representative Supervisor staging must still establish
the actual deployed permission/path behavior before LIVE.

The subject comes only from trusted Ingress request identity. Pep resolves its
final Health identity, including deleted, deactivated and unmapped users.
Getfit's workout mapping, display names, browser selectors, cookies and a default
person cannot supply Health identity. Missing or spoofed identity fails closed.

## Signing key and private-file boundary

The administrative options are `pep_health_signing_kid` and the password field
`pep_health_signing_private_key`. Use one active `kid` and its matching raw
32-byte Ed25519 private key encoded as canonical base64url. This is a private
seed, not a PEM file or the public key. Do not paste keys, assertions, subjects,
mappings or Health payloads into diagnostics or review artifacts.

When enabled, `run.sh` creates a fresh temporary file under `/data` with an
owner-only umask, writes the option without tracing, sets mode `0600` and replaces
`/data/pep-health-signing.key` without following an existing destination symlink.
It exports `HWA_PEP_HEALTH_SIGNING_KEY_FILE` and the non-secret
`HWA_PEP_HEALTH_SIGNING_KID`; it unsets the inline private-key environment value.
Python loads that file once when constructing the reader. It rejects missing,
empty, symlinked, non-regular, oversized, malformed or non-32-byte input and, on
POSIX, group/world-readable files. Failed key materialization leaves the path
unset, so Health becomes unavailable while workouts can still be served.

For an isolated runtime outside the add-on, the equivalent inputs are
`HWA_PEP_HEALTH_ENABLED`, `HWA_PEP_HEALTH_SIGNING_KID`, the private file path in
`HWA_PEP_HEALTH_SIGNING_KEY_FILE`, and the private Supervisor credential.
H6 does not authorize installing these on LIVE. Protect administrative options,
the private file and backups as secret material. Turning Health off stops key
loading and calls; it does not claim to erase the administrative option or an
existing private file.

## Stable unavailable behavior

These are internal reason classes for verification; the browser receives safe
unavailable presentation, without raw frames, exception text, identity or keys.

| Condition | Internal reason |
| --- | --- |
| Getfit activation is off | `GETFIT_PEP_HEALTH_DISABLED` |
| Enabled signing/token configuration is invalid | `PEP_HEALTH_CONFIGURATION_INVALID` |
| Pep authority is off | `HEALTH_AUTHORITY_DISABLED` |
| Pep's startup assertion quarantine | `SERVICE_ASSERTION_STARTUP_QUARANTINE` |
| Invalid, unknown or removed signing key/assertion | `INVALID_SERVICE_ASSERTION` |
| Subject cannot resolve to an available Pep person | `PERSON_CONTEXT_UNAVAILABLE` |
| Assertion rate limit | `ASSERTION_RATE_LIMITED` |
| Connection, protocol, timeout, compute or integrity failure | `PEP_HEALTH_UNAVAILABLE` |

Each read creates a fresh assertion with a fresh JTI and a 30-second validity,
then attempts one connection and one service command within a five-second
production deadline. Getfit does not retry, sleep on `Retry-After` or retain a
successful projection across requests. Cancellation propagates after connection
cleanup. Response schema, authority, no-store metadata and person/profile
isolation must validate completely; any failure discards the current projection.
Health unavailability never supplies a Person A/Person B fallback.

## One-key rotation, Pep overlap and revocation

Getfit loads exactly one private key and `kid` per reader. Pep can hold multiple
verifier public keys during a governed overlap; Getfit never tries a second key.
The following is the operational sequence for separately authorized staging or
LIVE work, not authorization to perform it:

1. Add the new public key and distinct `kid` to Pep while retaining its old key.
   Apply Pep's configuration/reload procedure and respect its 35-second startup
   assertion quarantine before checking service acceptance.
2. Configure Getfit's matching new private key and active `kid`, then restart
   Getfit to construct its new single signer.
3. Verify the new signer against the trusted subject path and Pep's final mapping
   in representative staging. Verify that workouts remain usable during denial.
4. Remove the old public key from Pep after the agreed overlap window and reload
   Pep. Respect the 35-second quarantine and prove the removed `kid` is rejected.

For emergency revocation, remove the affected public key from Pep, disable
Getfit Health and reload Pep. The revoked assertion must be rejected; Getfit
presents unavailable and does not switch keys automatically. No real key,
identity or payload belongs in the resulting evidence.

## Rollback and outstanding gates

Runtime rollback sets `pep_health_enabled=false` and restarts Getfit. No Health
key is loaded or assertion issued; no stale/local Health path appears. Pep can
independently roll its authority flag back, which returns an authority-disabled
denial that Getfit presents as unavailable. Rollback does not rewrite workout
evidence or correction history.

Local synthetic Supervisor-boundary proof and isolated real Core-image service
proof have different scopes. Neither proves a deployed Supervisor + Getfit +
Pep topology. Representative pre-LIVE staging still needs trusted Ingress
identity, spoof rejection, actual proxy/token/service operation, Pep mapping,
clock skew, key overlap/revocation and deleted/deactivated/unmapped isolation.
The exact provider QA/current candidate image gate is **BLOCKED** pending
authoritative identity evidence. Independent whole-branch architecture/security/
privacy review accepted `29dfdd6` on 2026-10-12 with no Critical/Important finding;
its minor Retry-After wording discrepancy is corrected in the design. Independent
review and exact-head QA/hosted CI for subsequent changes remain outstanding.

Use the [staging L1 acceptance runbook](../docs/superpowers/evidence/2026-10-12-getfit-h6-staging-l1-acceptance.md)
only in an explicitly authorized disposable non-LIVE environment. It has not
been executed. Enabling Pep server Health authority there requires explicit
non-LIVE authorization; missing staging must never be replaced by LIVE. Neither
the historical 2026.9.4 nor supplemental 2026.10.0 Core proof closes the unknown
exact f61 QA/current candidate image gate or the representative L1 gate.

Merge has an additional automatic-publication blocker. The current
`.github/workflows/release.yml` listens for completed CI and initializes release
only after successful **push** CI on **main**. Its downstream jobs publish amd64
and aarch64 architecture images and the production version/latest multi-arch
manifest. No LIVE-sensitive publication or deployment is authorized here, so
merge remains blocked; do not disable or change the workflow to bypass that
boundary. A feature-branch push triggers CI; the Release workflow may receive
its completion event, but its main-only initialization condition is false.
Release and production-artifact acceptance gates remain unclosed.

See the [H6 evidence](../docs/superpowers/evidence/2026-10-08-getfit-h6-contract-evidence.md)
for actual commands, image provenance and limitations. The earlier Task 9
continuation on 2026-10-11 authorized local documentation and verification only;
it did not authorize push, PR changes, merge or release. The current 2026-10-12
scope separately grants the controller fast-forward publication and PR updates
subject to verification and the applicable gates. This documentation worker does
not publish. Merge remains blocked by the automatic production-publication
boundary above; the exact-image and production/release gates remain unclosed.
No LIVE access/configuration, deployment, activation, H6S or H7 is authorized.
No H6 completion claim follows from local tests alone.
