# Getfit production release gate

A Getfit production release is allowed only from the exact commit that passed every gate below. Do not publish or install a different head and do not treat an earlier green run as evidence for a later commit.

## Exact-head quality gate

The candidate exact-head commit must pass, from a clean checkout:

- `uv sync --dev`
- `uv run ruff check .`
- `uv run mypy src`
- `uv run pytest tests/unit -q`
- `uv run pytest tests/integration -q`
- `uv run pytest tests/contract -q`
- `uv run pytest tests/e2e -q`
- `rm -f hwa.db && uv run alembic upgrade head`
- `docker build -t getfit-release-candidate .`

The GitHub CI workflow is permanent release evidence for these checks. A release must not be cut while any required job is pending, skipped unexpectedly or failing.

## Whole-product acceptance

Before publication, permanent QA must prove:

1. **Kris training journey** — Today can start an approved workout; autosave preserves strength/cardio draft evidence; restart resumes the same server-owned draft; completion creates immutable evidence; Progress/History shows the completed session; the Pep workout provider exposes the effective workout revision.
2. **Kirsty isolation** — Kirsty resolves only to Kirsty, never inherits Kris's active draft, display state, authority IDs or browser-selected identity, and cannot read Kris-owned workout evidence.
3. **Corrections and export** — correction creates a later immutable revision; the earlier revision remains historical; only the latest effective revision is projected to Pep, with `supersedes_revision_number` and the effective atomic evidence ID.
4. **Restart recovery** — persistent `/data/hwa.db` survives application restart and Alembic migration startup without discarding an active draft or completed history.
5. **Home Assistant identity** — Supervisor Ingress identity is accepted only from the trusted ingress source; direct spoofed identity headers and unmapped users fail closed.
6. **Degraded dependencies** — unavailable Pep Health or Menu-Nutrition context must not block the authoritative Getfit workout flow. Missing physiological evidence remains `UNAVAILABLE`; it is never estimated. Missing optional technique/media context must degrade without loss of workout data.
7. **Responsive/touch use** — the five primary surfaces (Today, Workout, Progress, Library, Settings) retain the mobile viewport contract and primary/live controls provide at least 44 px touch targets.
8. **Equipment semantics** — treadmill supports speed/incline up to the configured installation limit; spin bike supports cadence/resistance and never exposes incline; adjustable dumbbells do not acquire cardio fields.

## Home Assistant package gate

The release commit must contain:

- root `repository.yaml`;
- `getfit/config.yaml` with the release version;
- `image: ghcr.io/ktgregson93-collab/getfit`;
- Supervisor Ingress enabled on internal port `8099`;
- production startup through `run.sh` using `/data`, migrations before Uvicorn, and `hwa.runtime:app`;
- a container image that builds successfully from the same exact-head commit.

The published container tag must exactly match `getfit/config.yaml` `version`. Verify that the GHCR tag is publicly pullable before calling the release installable.

## Production publication and install

Merge does not publish an image. The `Release` workflow accepts only a manual
`workflow_dispatch` on `main`. Its full `source_sha` must equal both the dispatch
commit and current repository `main`. The latest main-push `CI` run at that SHA
must be completed/successful, including the required `quality` job and every
other job in its latest attempt. Earlier green commits, PR merge refs, incomplete
job inventories and API failures deny publication. The initiating operator and
the actor requesting a rerun must each have GitHub maintain/admin permission.
Guards run on GitHub-hosted runners before writable builder steps and again
before the combined manifest. They never execute on a LIVE runner.

Before dispatch, an independent reviewer must record and review exact-source
staging, compatibility, security and rollback acceptance. Supply four distinct
same-repository acceptance-comment URLs as `staging_evidence`,
`compatibility_evidence`, `security_evidence` and `rollback_evidence`. Every
input must use this form:
`https://github.com/ktgregson93-collab/Getfit/issues/<issue-id>#issuecomment-<comment-id>`.
For every named gate, an independent maintain/admin reviewer (neither the
initiating nor rerun operator) must record these exact standalone lines, with
the applicable gate and full source SHA:

```text
release-acceptance: staging
source-sha: <full source SHA>
decision: accepted
```

Use `compatibility`, `security` and `rollback` in their respective comments.
Each comment must independently accept the actual evidence for that named gate;
a generic acceptance, an operator's own comment, a stale SHA or a run-only URL
cannot satisfy the gate. A reviewer may link supporting successful runs in the
comment body using
`https://github.com/ktgregson93-collab/Getfit/actions/runs/<run-id>`.
The helper checks every such linked same-repository run's completed/successful
status, exact source SHA and all jobs in its latest attempt. Successful runs
remain supporting evidence and cannot replace the reviewer's named-gate
acceptance. Reviewers must inspect actual tests, staging outcomes, compatibility,
security and rollback readiness before recording acceptance. Never invent a
reference or acceptance decision to satisfy the workflow.

Separately authorize and carry out the LIVE Home Assistant change to disable
Getfit automatic update before merging version-bearing app-store metadata and
before publication, and verify it actually took effect. Changing the version in
`main` can make Supervisor attempt an automatic update even when the matching
image has not yet been published. Prevent those metadata-triggered attempts as
well as actual deployments; the merge gate must check the disabled state too.
Dispatch requires `auto_update_disabled=true`. This is an operator attestation;
the publication workflow cannot inspect LIVE settings. Publication and
installation remain blocked until the acceptance evidence and disabled
auto-update state are real. Publishing a tag while LIVE auto-update is enabled
can cause an unintended production update even without an installation command.

Release runs are serialized with cancellation disabled. Before any write the
workflow checks the version across app config, package, runtime, companion
manifest and Dockerfile and checks all three version tags absent using both
authenticated GHCR pull access and anonymous access. Only a valid
`MANIFEST_UNKNOWN` response establishes absence; authorization failures, registry
outages and malformed responses deny publication. A public 404 alone cannot
establish that an inaccessible private version is absent.

The next governed quality-foundation version is reserved as `0.1.40`: a read-only
anonymous inventory on 2026-10-12 found `MANIFEST_UNKNOWN` for `getfit:0.1.40`,
`amd64-getfit:0.1.40` and `aarch64-getfit:0.1.40`. This inventory is a point-in-time
reservation, not publication authority; dispatch rechecks both access modes.
`0.1.39` is historical and must never be overwritten.

The pinned Home Assistant builder supports additional `build-args` and returns a
built digest ([pinned action source](https://github.com/home-assistant/builder/blob/7412f0023ea9b6e58e8bb5059f1660f51376f49a/actions/build-image/action.yml)).
The workflow passes `BUILD_REVISION` from the full dispatch SHA. It publishes
version tags only; it does not move any `latest` tag. Each successful architecture
build must anonymously verify its own digest and exact revision/version/arch
labels before its digest receipt is uploaded. The combined manifest is published
only after both receipts match the actual architecture images, including any
single-architecture BuildKit indexes. Final verification joins the anonymous
combined index to the expected Linux amd64/arm64 manifests and config blobs,
checks their revision/version labels, retains a JSON digest/provenance artifact,
and performs clean anonymous pulls by the verified index digest for both
architectures. A source URL or old version image is
insufficient provenance.

If any build or verification fails, publication is not certified and installation
is blocked. A partial architecture publication can leave immutable version tags
behind. Do not delete or overwrite them and do not rerun expecting
skip-existing-as-success: investigate the failure, reserve a newly inventoried
unused version in the version files, review that source and repeat its gates.
Repository concurrency prevents competing release runs; it cannot exclude
out-of-band registry writers. Operators must prevent those during publication.

After the full manual publication workflow succeeds, installation is a separate
controlled, explicitly authorized action:

1. Retain the previous known-good version/digests and a verified cold backup of
   `/data` before updating. Rehearse rollback in staging, including restoring the
   old image and data when migrations make a simple image downgrade unsafe.
   Never run migration tests against an owner's existing database.
2. Confirm automatic update remains disabled. Preserve existing person mappings,
   keys and default-off Pep Health configuration; publication does not activate
   H6 or any downstream authority.
3. Add the Getfit custom repository if necessary and install the verified version
   through Home Assistant only after explicit install authorization.
4. Verify startup migrations against the intended instance, authenticated person
   isolation, Settings equipment capability, draft recovery and completed history.
   Open through Ingress and smoke-check each primary surface without changing
   owner workout evidence.
5. Record default-off acceptance and the observed installation version/digests.
   If acceptance fails, stop and execute the approved rollback using the retained
   image and cold backup. Re-enabling automatic update requires its own decision.

Do not call the instance live until the authorized Home Assistant installation
and post-start acceptance have actually succeeded. This workflow repair grants
no publication, installation, LIVE settings or workflow-dispatch authorization.

## Authority boundary

Publishing Getfit does **not** activate Pep Health as a progression authority and does not grant Pep-Site or Menu-Nutrition mutation authority. Read-only presentation context and the versioned workout-source export remain within their approved contracts. Any new LIVE Pep Health activation, cross-system mutation or changed authority relationship requires separate explicit approval and its own acceptance evidence.
