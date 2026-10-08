# Getfit H6 Health Context Production Binding Design

**Status:** Proposed for review

**Scope:** H6 production-capable, read-only Getfit binding to Pep Health Context

**Getfit authority base:** `2dd07e7ea214fb8e54ff381e4012180b3c90e90a`

**Pep contract base:** `f61b9644a88c5047176e87d4a7edf2939e218d32`

**LIVE status:** NOT DEPLOYED / NOT ENABLED

## 1. Decision

Getfit will call Home Assistant Core through the Supervisor WebSocket proxy and invoke the existing response-producing service:

```text
browser request
  -> trusted Supervisor Ingress principal
  -> Getfit request-scoped Health read
  -> ws://supervisor/core/websocket
  -> peptide_site.get_health_context({assertion})
  -> Pep resolves assertion subject to Pep person
  -> closed peptide-site.health-context v1 projection
  -> Getfit presentation-only projection
```

This is the H0-selected service-assertion path. It does not use Pep's interactive browser endpoint, fabricate Ingress headers, call Pep directly, or introduce a second Health transport.

H6 adds production capability only. `pep_health_enabled` defaults to false, Pep's `server_health_authority_enabled` remains independently controlled, and no LIVE configuration, mapping, key installation, deployment, or activation is part of H6 implementation.

## 2. Reconciled current state

### Getfit

- `HomeAssistantIngressPrincipalProvider` accepts `X-Remote-User-Id` only from the Supervisor Ingress source and produces an `AuthenticatedPrincipal`.
- `IdentityService` separately maps that principal to Getfit's internal `PersonContext`; this local mapping remains useful for response isolation checks but is not sent to Pep.
- `PepHealthReader` already owns the closed Pydantic projection model, schema/version/authority checks, person/profile mismatch checks, and fail-closed `PepHealthContext` result.
- `_external_context` already treats Pep Health as optional, request-scoped presentation context. `build_external_context` exposes only approved values and cannot alter workout authority.
- Production does not construct a Pep reader today. Its current default URL points at Pep's interactive route and is therefore not the H6 service path.
- Getfit has no Health cache, no Health calculation engine, and no production assertion signer.

### Pep

- Domain/service: `peptide_site.get_health_context`.
- Service input is exactly one required `assertion`; person, profile, source and user selectors are rejected.
- The service returns `{status_code, body, headers}` inside the Home Assistant service response.
- Success body is the closed `peptide-site.health-context` schema version `1`, authority `PEPTIDE_SITE_HEALTH`, with `automatic_action=false` and `causation_asserted=false`.
- Every governed response carries `Cache-Control: no-store`.
- Pep verifies Ed25519/EdDSA assertions with `typ=H0-SA`, issuer `getfit`, audience `peptide-health-read`, a mandatory matching `kid`, HA user subject, `iat`, `exp`, and unique `jti`.
- Maximum assertion lifetime is 30 seconds, ordinary skew tolerance is 5 seconds, and a Pep verifier restart starts a 35-second assertion quarantine.
- Pep accepts a configured public-key set, enabling overlap during rotation; unknown or removed `kid` values fail as `INVALID_SERVICE_ASSERTION`.
- Pep performs the final HA-user-to-Pep-person resolution. System/Supervisor identity is never treated as the Health person.

The current Getfit reader models remain reusable, but the direct `GET /api/peptide_site/health-context` request is not.

## 3. Trust and principal flow

The browser supplies no Health identity. The existing web dependency resolves the trusted Ingress principal once and retains it only in request state alongside the already-resolved `PersonContext`.

The Health reader receives:

- `ha_user_id`: copied from the trusted `AuthenticatedPrincipal.subject_id`;
- `expected_person_id` and `expected_health_profile_id`: internal values used only to reject a mismatched response.

Only `ha_user_id` enters the signed assertion. No Getfit, Pep-person, profile, source, entity or selector value is sent in the service command. Pep verifies the assertion, looks up the real HA user, and resolves its own mapping authority before calculation.

If request state does not contain the trusted principal, Health is unavailable. Getfit must not recover identity from query parameters, cookies, browser payloads, display names, its local Pep mapping, or Person A defaults.

## 4. Assertion creation

Getfit adds a small production signer using `cryptography`'s Ed25519 implementation. For every service attempt it creates a new assertion:

```json
header: {"alg":"EdDSA","kid":"<active-kid>","typ":"H0-SA"}
claims: {
  "iss":"getfit",
  "aud":"peptide-health-read",
  "sub":"<trusted-ha-user-id>",
  "iat":<utc-epoch-seconds>,
  "exp":<iat + 30>,
  "jti":"<cryptographically-random-id>",
  "kid":"<active-kid>"
}
```

Header and claims use deterministic compact JSON and unpadded base64url. The signature covers `encoded_header.encoded_claims`. The signer rejects blank subjects and invalid clocks before signing. Assertions are never reused, persisted or returned to the browser.

## 5. Key loading and storage

The active signing configuration consists of one `kid` plus one raw 32-byte Ed25519 private key encoded as base64url. The add-on option is a password field. The launch script materialises it under `/data` with owner-only permissions and exports only the key-file path and non-secret `kid`; it does not print the value. Production Python:

- rejects a missing, empty, symlinked, non-regular, oversized, group/world-readable, malformed or non-32-byte key file;
- reads it once during application construction;
- constructs the Ed25519 signer and retains only the signer object;
- never serves the file through static paths or application routes;
- records only a stable configuration state code on failure.

If Health activation is false, Getfit does not require or load a key. If activation is true and signing configuration is invalid, workout serving remains available while Health fails closed as `PEP_HEALTH_CONFIGURATION_INVALID`; the process does not silently downgrade to the legacy HTTP reader.

`SUPERVISOR_TOKEN` is a separate system credential. It is read from the environment only by the HA WebSocket client and is never used as person identity, persisted, logged, or exposed to the browser.

## 6. Rotation and revocation

Pep already supports multiple verifier public keys. Governed rotation is:

1. add the new public key and `kid` to Pep while retaining the old key;
2. configure Getfit's active `kid` and matching private key, then restart Getfit;
3. prove successful reads use the new `kid` without logging the assertion or subject;
4. remove the old public key from Pep after the overlap window and reload Pep;
5. observe Pep's required 35-second assertion quarantine and prove the old key is rejected.

Emergency revocation removes the public key from Pep, disables Getfit Health, and reloads Pep. Health becomes unavailable; workouts remain usable. Getfit never tries another private key automatically. Key installation, rotation and revocation on LIVE are operational steps outside this PR and require separate approval.

## 7. HA WebSocket invocation

The add-on declares `homeassistant_api: true`, which grants access to the documented Supervisor Core proxy. The client connects to `ws://supervisor/core/websocket`, authenticates with `SUPERVISOR_TOKEN`, and sends one command:

```json
{
  "id": 1,
  "type": "call_service",
  "domain": "peptide_site",
  "service": "get_health_context",
  "service_data": {"assertion": "<short-lived-assertion>"},
  "return_response": true
}
```

The command contains no `target`, person ID, profile ID, source selector, fabricated Ingress header, or browser-originated authority field. A connection is opened per Health read and closed on success, failure, timeout or cancellation. H6 does not add a background connection, worker or queue.

This matches current Home Assistant app support: `homeassistant_api: true` enables the Core proxy, the Supervisor token authenticates its WebSocket proxy, and `call_service` with `return_response: true` returns response-producing service data. Compatibility is gated against the repository's Python 3.12 Home Assistant app image and the current target HA/Supervisor staging topology before any LIVE activation.

## 8. Response-envelope parsing

The client accepts only a matching WebSocket `result` message with `success=true`, then requires `result.response` to contain:

- `status_code`: an integer, never a boolean;
- `body`: an object;
- `headers`: a string-to-string object containing `Cache-Control: no-store`.

For governed `200`, `body` is passed to the existing closed v1 model and person/profile isolation checks. Extra fields, type confusion, wrong schema/version/authority, `automatic_action` other than false, `causation_asserted` other than false, or mismatched person/profile all yield unavailable with no partial context.

For non-200 envelopes, Getfit retains only an allowlisted stable reason. Raw WebSocket errors, Home Assistant error messages, exception text and response bodies are discarded. Unknown or malformed envelopes become `PEP_HEALTH_UNAVAILABLE`.

## 9. Activation, availability, timeout and retry

Activation and availability remain separate:

- `pep_health_enabled=false`: no key load, no assertion and no WebSocket call; Health is unavailable with `GETFIT_PEP_HEALTH_DISABLED`.
- Getfit enabled while Pep authority disabled: Pep returns `503 HEALTH_AUTHORITY_DISABLED`; Getfit drops the current response and presents unavailable.
- Pep startup quarantine: `503 SERVICE_ASSERTION_STARTUP_QUARANTINE` plus bounded `Retry-After`; Getfit presents unavailable for the current request.
- invalid assertion: `401 INVALID_SERVICE_ASSERTION`; unavailable, no retry.
- unmapped/deleted/deactivated subject: `403 PERSON_CONTEXT_UNAVAILABLE`; unavailable, no retry.
- rate limit: `429 ASSERTION_RATE_LIMITED`; unavailable for the current request.
- compute/overload/rebuild/integrity failure, connection failure, protocol failure or timeout: unavailable for the current request.

One end-to-end monotonic timeout covers connect, authentication, command and response. H6 performs no in-request automatic retry. A retry would require a fresh assertion and is naturally performed by a later user request. In particular, authority-disabled, authentication and person failures are never retried. `Retry-After` is parsed only as bounded diagnostic metadata and never sleeps a request for the 35-second quarantine.

## 10. Cache and person isolation

H6 has no cross-request Health cache. The Pep projection and assertion exist only for one read and are released after presentation projection. Consequently:

- a person switch always signs a new assertion for the new trusted HA subject;
- a failed or disabled read cannot expose the prior person's context;
- no stale successful projection survives an error or authority rollback;
- the existing internal person/profile checks remain defence in depth, not mapping authority.

Pep's server cache remains the cache of record. Adding a Getfit cache later requires a separate reviewed design.

## 11. Presentation and authority boundary

The existing `PepHealthContext -> ExternalContext` projection remains the only browser-facing path. It exposes approved presentation values such as body mass and sleep duration and retains `presentation_only=true` and `automatic_action=false`.

Getfit does not calculate readiness, progress, Journey, body composition, BMI, trend, risk, or recommendations. It does not substitute local values or reinterpret unavailable states. Pep outage never blocks workout authority, draft durability, completion or correction; it only removes the optional Health presentation context.

Pep's current Health authority implementation contains no synchronous Getfit callback in its calculation/provider path. The H6 read therefore does not create a Getfit -> Pep -> Getfit dependency cycle. Permanent QA will guard that the client makes only the single HA service call and that Pep Health failure cannot call or alter Getfit workout services.

## 12. Logging and privacy

Logs and diagnostics may contain only stable state codes and aggregate transport outcomes. They must not contain:

- Supervisor token or signing private/public key bytes;
- assertion, signature, `jti`, HA user ID, Pep person/profile ID;
- Health projection/body/metrics;
- Home Assistant raw error messages, response bodies or exception representations.

Permanent caplog tests use sentinel values for each secret/identity/payload class and assert absence on success, protocol error, validation error and cancellation.

## 13. Lifecycle and cleanup

Application construction creates an immutable signer and WebSocket client configuration only when Getfit Health is enabled. Each read owns its connection and closes it in `finally`/async-context cleanup. Cancellation propagates after cleanup and is not converted into a normal retry. No task, socket, assertion, payload or retry timer remains after the request.

Application shutdown therefore has no background Health resource to drain. Tests still prove connection closure across all exit paths.

## 14. Permanent QA and release gates

RED tests must first prove the current production runtime cannot perform the governed service read. Permanent coverage then proves:

- trusted Ingress subject is the assertion subject;
- direct/spoofed/browser identity cannot reach the signer;
- canonical Ed25519 assertion format, 30-second lifetime, unique `jti` and active `kid`;
- exact selector-free WebSocket command and response request;
- strict HA envelope and v1 projection parsing, including boolean/type confusion;
- person/profile mismatch and sequential person-switch isolation;
- activation-disabled, authority-disabled, quarantine, invalid assertion, rate-limit, timeout, cancellation and malformed response behavior;
- no retry where prohibited and a fresh assertion on each later attempt;
- zero cross-request Health cache and no legacy/direct-HTTP fallback;
- key-file permissions/format checks, rotation overlap and removed-`kid` rejection fixtures;
- privacy/logging sentinel absence;
- workout pages and lifecycle remain usable when Health is unavailable;
- no Health calculations or workout dependency cycle;
- add-on config grants only the required HA Core API permission and keeps activation false by default.

Release verification is Ruff, strict mypy, all unit/integration/contract/e2e suites, migrations, container build, exact-head CI, whole-branch review, zero unresolved review threads, and a cross-repository contract check pinned to the Pep SHA above. H6S soak and every LIVE gate remain separate.

## 15. Rollback and exclusions

Code rollback is the default-false Getfit activation flag. Runtime rollback turns Getfit Health off; no assertion is created and no old/local Health path becomes visible. Pep's independent authority rollback returns `HEALTH_AUTHORITY_DISABLED`, which Getfit treats identically as unavailable for presentation while preserving the explicit reason internally.

Excluded from H6:

- enabling either authority in LIVE;
- installing, rotating or revoking LIVE keys;
- changing Pep mappings, Health data, ledger or configuration;
- H6S joint soak;
- H7 legacy-engine retirement;
- any Health mutation, automated workout action or causation claim.

**LIVE changes: none.**
