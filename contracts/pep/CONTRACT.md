# Pep Health Context v1 compatibility snapshot

- Source repository: https://github.com/PArkDevolpments/Pep-Site
- Provider commit: `f61b9644a88c5047176e87d4a7edf2939e218d32`
- Source path: `schemas/health_context_v1.schema.json`
- SHA-256: `e37dc67d7aa921abc94942e8450622c93c172097c1a8a233fd567b33b69a0522`
- Git blob: `a40d66b82796f93ff5b8c5c9f6a6e1b4750b9301`

`health_context_v1.schema.json` preserves the exact provider bytes. It is a
consumer compatibility fixture, never mapping or Health authority. Pep alone
calculates, interprets and resolves Health readiness, progress and Journey.
Getfit remains authoritative only for workout prescription and performed evidence.

The production read binds a trusted Supervisor Ingress HA subject to a fresh
assertion and calls `peptide_site.get_health_context` through HA WebSocket.
No person, profile or source selector is sent. Expected local person/profile
identifiers are used only to reject mismatched responses; they do not select
Pep's identity. No default person, cross-person fallback, local Health fallback,
cross-request cache, or Health mutation is permitted.

A matching successful WebSocket result must contain `result.response` with an
integer (not boolean) `status_code`, object `body`, and string headers including
`Cache-Control: no-store`. Governed 200 bodies must satisfy the closed v1
projection and preserve `automatic_action=false` and `causation_asserted=false`.
Invalid responses expose no partial context. Governed errors retain only
allowlisted reasons; raw payloads, identity, credentials and exception messages
must never enter logs. Fixtures are entirely synthetic.

This checkpoint intentionally leaves tests RED for missing service binding and
strict type rejection. It adds no production implementation. Health activation
remains independently disabled by default; no LIVE deployment, H6S or H7 work is
authorized by this snapshot.
