"""Execute release policy against synthetic API/registry boundary responses in CI."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SHA = "a" * 40
REPO = "ktgregson93-collab/Getfit"
VERSION = "0.1.40"


def test_manual_release_policy_exists():
    assert (ROOT / "_tools/release_policy.py").is_file()


@pytest.fixture
def policy():
    path = ROOT / "_tools/release_policy.py"
    assert path.is_file(), "manual release policy has not been implemented"
    spec = importlib.util.spec_from_file_location("release_policy", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def candidate():
    return {
        "event": "workflow_dispatch",
        "ref": "refs/heads/main",
        "sha": SHA,
        "source_sha": SHA,
        "repository": REPO,
        "actor": "operator",
        "triggering_actor": "rerunner",
        "auto_update_disabled": "true",
        "evidence": {
            gate: f"https://github.com/{REPO}/actions/runs/{number}"
            for number, gate in enumerate(("staging", "compatibility", "security", "rollback"), 10)
        },
    }


@pytest.fixture
def api():
    run = {
        "id": 7,
        "run_number": 100,
        "run_attempt": 2,
        "head_sha": SHA,
        "head_branch": "main",
        "event": "push",
        "name": "CI",
        "status": "completed",
        "conclusion": "success",
        "repository": {"full_name": REPO},
    }
    values = {
        "/branches/main": {"commit": {"sha": SHA}},
        "/collaborators/operator/permission": {"permission": "write", "role_name": "maintain"},
        "/collaborators/rerunner/permission": {"permission": "admin", "role_name": "admin"},
        "/actions/workflows/ci.yml/runs?event=push&branch=main&per_page=1": {
            "total_count": 100,
            "workflow_runs": [copy.deepcopy(run)],
        },
        "/actions/runs/7": run,
        "/actions/runs/7/attempts/2/jobs?per_page=100": {
            "total_count": 1,
            "jobs": [
                {"name": "quality", "status": "completed", "conclusion": "success", "head_sha": SHA}
            ],
        },
    }
    for number in range(10, 14):
        values[f"/actions/runs/{number}"] = dict(run, id=number, name="Recorded gate")
        values[f"/actions/runs/{number}/attempts/2/jobs?per_page=100"] = copy.deepcopy(
            values["/actions/runs/7/attempts/2/jobs?per_page=100"]
        )

    def fetch(path):
        return copy.deepcopy(values[path])

    fetch.values = values
    return fetch


def test_valid_manual_operator_and_rerun_authorization(policy, candidate, api):
    assert policy.authorize(candidate, api, [VERSION] * 5) == VERSION


@pytest.mark.parametrize(
    "field,value",
    [
        ("event", "workflow_run"),
        ("ref", "refs/pull/101/merge"),
        ("sha", "b" * 40),
        ("source_sha", "b" * 40),
        ("source_sha", "a" * 7),
        ("auto_update_disabled", "false"),
        ("auto_update_disabled", ""),
        ("actor", ""),
        ("triggering_actor", ""),
        ("repository", "other/repo"),
    ],
)
def test_bad_dispatch_denied(policy, candidate, api, field, value):
    candidate[field] = value
    with pytest.raises(policy.Denied):
        policy.authorize(candidate, api, [VERSION] * 5)


@pytest.mark.parametrize("actor", ["operator", "rerunner"])
@pytest.mark.parametrize(
    "permission,role",
    [("write", "write"), ("read", "maintain"), ("maintain", "maintain"), (None, None)],
)
def test_unprivileged_initiator_or_rerunner_denied(policy, candidate, api, actor, permission, role):
    api.values[f"/collaborators/{actor}/permission"] = {"permission": permission, "role_name": role}
    with pytest.raises(policy.Denied):
        policy.authorize(candidate, api, [VERSION] * 5)


@pytest.mark.parametrize(
    "change",
    [
        "main",
        "old_ci",
        "pr_ci",
        "pending",
        "failed",
        "skipped_job",
        "missing_job",
        "wrong_attempt",
        "api_error",
    ],
)
def test_stale_or_incomplete_ci_denied(policy, candidate, api, change):
    run = api.values["/actions/runs/7"]
    jobs = api.values["/actions/runs/7/attempts/2/jobs?per_page=100"]
    if change == "main":
        api.values["/branches/main"]["commit"]["sha"] = "b" * 40
    elif change == "old_ci":
        run["head_sha"] = "b" * 40
    elif change == "pr_ci":
        run["event"] = "pull_request"
    elif change == "pending":
        run["status"] = "in_progress"
    elif change == "failed":
        run["conclusion"] = "failure"
    elif change == "skipped_job":
        jobs["jobs"][0]["conclusion"] = "skipped"
    elif change == "missing_job":
        jobs["jobs"] = []
    elif change == "wrong_attempt":
        run["run_attempt"] = 3
    else:
        api.values["/branches/main"] = None
    with pytest.raises(policy.Denied):
        policy.authorize(candidate, api, [VERSION] * 5)


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "https://evil.example/accept",
        "https://github.com/other/repo/actions/runs/10",
        "https://github.com/ktgregson93-collab/Getfit/issues/1",
    ],
)
def test_evidence_reference_required(policy, candidate, api, bad):
    candidate["evidence"]["staging"] = bad
    with pytest.raises(policy.Denied):
        policy.authorize(candidate, api, [VERSION] * 5)


def test_failed_evidence_run_denied(policy, candidate, api):
    api.values["/actions/runs/10"]["conclusion"] = "failure"
    with pytest.raises(policy.Denied):
        policy.authorize(candidate, api, [VERSION] * 5)


def test_one_ci_run_cannot_substitute_for_all_independent_gate_references(policy, candidate, api):
    candidate["evidence"] = dict.fromkeys(candidate["evidence"], candidate["evidence"]["staging"])
    with pytest.raises(policy.Denied):
        policy.authorize(candidate, api, [VERSION] * 5)


@pytest.mark.parametrize(
    "mutation", [None, "self_approval", "wrong_sha", "not_accepted", "unprivileged"]
)
def test_independent_exact_source_acceptance_comments(policy, candidate, api, mutation):
    reference = f"https://github.com/{REPO}/issues/20#issuecomment-50"
    candidate["evidence"]["staging"] = reference
    comment = {
        "html_url": reference,
        "user": {"login": "reviewer"},
        "body": f"release-acceptance: staging\nsource-sha: {SHA}\ndecision: accepted",
    }
    api.values["/issues/comments/50"] = comment
    api.values["/collaborators/reviewer/permission"] = {
        "permission": "write",
        "role_name": "maintain",
    }
    if mutation == "self_approval":
        comment["user"]["login"] = "operator"
    elif mutation == "wrong_sha":
        comment["body"] = comment["body"].replace(SHA, "b" * 40)
    elif mutation == "not_accepted":
        comment["body"] = comment["body"].replace("decision: accepted", "decision: pending")
    elif mutation == "unprivileged":
        api.values["/collaborators/reviewer/permission"] = {
            "permission": "write",
            "role_name": "write",
        }
    if mutation is None:
        assert policy.authorize(candidate, api, [VERSION] * 5) == VERSION
    else:
        with pytest.raises(policy.Denied):
            policy.authorize(candidate, api, [VERSION] * 5)


@pytest.mark.parametrize("mutation", ["timeout", "non_json", "missing_run", "partial_jobs"])
def test_api_uncertainty_denies_publication(policy, candidate, api, mutation):
    def uncertain(path):
        if mutation == "timeout":
            raise OSError("unavailable")
        if mutation == "non_json":
            return "invalid"
        if mutation == "missing_run":
            return {}
        if "/jobs?" in path:
            return {"total_count": 2, "jobs": [{"status": "completed", "conclusion": "success"}]}
        return api(path)

    with pytest.raises(policy.Denied):
        policy.authorize(candidate, uncertain, [VERSION] * 5)


def test_version_mismatch_or_preexisting_release_version_denied(policy, candidate, api):
    for versions in ([VERSION, "0.1.39"], ["0.1.39"] * 5, ["oops"] * 5):
        with pytest.raises(policy.Denied):
            policy.authorize(candidate, api, versions)


@pytest.mark.parametrize(
    "status,body",
    [
        (200, {"schemaVersion": 2}),
        (401, {}),
        (403, {}),
        (500, {}),
        (404, {"errors": [{"code": "NAME_UNKNOWN"}]}),
        (404, {}),
    ],
)
def test_registry_only_manifest_unknown_is_absent(policy, status, body):
    def registry(image, ref):
        return status, json.dumps(body).encode(), {}

    with pytest.raises(policy.Denied):
        policy.ensure_absent(registry, ["getfit", "amd64-getfit", "aarch64-getfit"], VERSION)


def test_absence_checks_each_image_and_uses_authenticated_inventory(policy):
    def anonymous(image, ref):
        return 404, b'{"errors":[{"code":"MANIFEST_UNKNOWN"}]}', {}

    def private(image, ref):
        return (200, b"{}", {}) if image == "aarch64-getfit" else anonymous(image, ref)

    policy.ensure_absent(anonymous, ["getfit", "amd64-getfit", "aarch64-getfit"], VERSION)
    with pytest.raises(policy.Denied):
        policy.ensure_absent(private, ["getfit", "amd64-getfit", "aarch64-getfit"], VERSION)


def image_fixture(config_change=None):
    objects = {}
    receipts = {}
    manifests = []
    for arch, platform in (("amd64", "amd64"), ("aarch64", "arm64")):
        config = {
            "os": "linux",
            "architecture": platform,
            "config": {
                "Labels": {
                    "org.opencontainers.image.revision": SHA,
                    "org.opencontainers.image.version": VERSION,
                    "io.hass.version": VERSION,
                    "io.hass.arch": arch,
                }
            },
        }
        if arch == "amd64" and config_change:
            label = {
                "revision": "org.opencontainers.image.revision",
                "version": "io.hass.version",
                "arch": "io.hass.arch",
            }[config_change]
            config["config"]["Labels"][label] = "wrong"
        config_raw = json.dumps(config).encode()
        config_digest = "sha256:" + hashlib.sha256(config_raw).hexdigest()
        manifest_raw = json.dumps(
            {"schemaVersion": 2, "config": {"digest": config_digest}}
        ).encode()
        digest = "sha256:" + hashlib.sha256(manifest_raw).hexdigest()
        objects[(f"{arch}-getfit", VERSION)] = manifest_raw
        objects[("getfit", digest)] = manifest_raw
        objects[("getfit", config_digest)] = config_raw
        objects[(f"{arch}-getfit", config_digest)] = config_raw
        receipts[arch] = digest
        manifests.append({"digest": digest, "platform": {"os": "linux", "architecture": platform}})
    objects[("getfit", VERSION)] = json.dumps({"schemaVersion": 2, "manifests": manifests}).encode()

    def registry(image, ref, kind="manifests"):
        raw = objects[(image, ref)]
        return 200, raw, {"Docker-Content-Digest": "sha256:" + hashlib.sha256(raw).hexdigest()}

    return registry, objects, receipts


def test_index_joins_build_digests_and_exact_config_provenance(policy):
    registry, _, receipts = image_fixture()
    policy.verify_image(registry, "getfit", VERSION, SHA, receipts)


def test_builder_single_arch_index_with_attestation_joins_leaf_in_combined_index(policy):
    registry, objects, receipts = image_fixture()
    for arch, platform in (("amd64", "amd64"), ("aarch64", "arm64")):
        manifest_digest = receipts[arch]
        objects[(f"{arch}-getfit", manifest_digest)] = objects[(f"{arch}-getfit", VERSION)]
        index = {
            "schemaVersion": 2,
            "manifests": [
                {"digest": manifest_digest, "platform": {"os": "linux", "architecture": platform}},
                {
                    "digest": "sha256:" + "f" * 64,
                    "platform": {"os": "unknown", "architecture": "unknown"},
                    "annotations": {"vnd.docker.reference.type": "attestation-manifest"},
                },
            ],
        }
        raw = json.dumps(index).encode()
        receipts[arch] = "sha256:" + hashlib.sha256(raw).hexdigest()
        objects[(f"{arch}-getfit", VERSION)] = raw
    policy.verify_image(registry, "getfit", VERSION, SHA, receipts)


def test_architecture_verification_does_not_require_unpublished_combined_tag(policy):
    registry, objects, receipts = image_fixture()
    del objects[("getfit", VERSION)]
    assert (
        policy.verify_image(registry, "getfit", VERSION, SHA, receipts, architectures_only=True)
        == receipts
    )


@pytest.mark.parametrize("authenticated", [False, True])
def test_real_registry_client_uses_separate_anonymous_and_authenticated_tokens(
    policy, monkeypatch, authenticated
):
    monkeypatch.setenv("GH_TOKEN", "synthetic-token")
    monkeypatch.setenv("GITHUB_ACTOR", "operator")
    calls = []

    def transport(url, headers):
        calls.append((url, headers))
        if "/token?" in url:
            return 200, b'{"token":"pull-token"}', {}
        return 404, b'{"errors":[{"code":"MANIFEST_UNKNOWN"}]}', {}

    monkeypatch.setattr(policy, "request", transport)
    policy.ensure_absent(policy.registry_client(authenticated), ["getfit"], VERSION)
    assert bool(calls[0][1].get("Authorization")) is authenticated
    assert "repository%3Aktgregson93-collab%2Fgetfit%3Apull" in calls[0][0]
    assert calls[1][1]["Authorization"] == "Bearer pull-token"
    assert calls[1][0].endswith("/getfit/manifests/0.1.40")


@pytest.mark.parametrize("status,body", [(401, b"{}"), (200, b"{}"), (200, b"bad")])
def test_authentication_failure_is_not_absence(policy, monkeypatch, status, body):
    monkeypatch.setenv("GH_TOKEN", "synthetic-token")
    monkeypatch.setenv("GITHUB_ACTOR", "operator")

    def transport(url, headers):
        return status, body, {}

    monkeypatch.setattr(policy, "request", transport)
    with pytest.raises(policy.Denied):
        policy.ensure_absent(policy.registry_client(True), ["getfit"], VERSION)


@pytest.mark.parametrize(
    "mutation", ["revision", "version", "arch", "receipt", "missing_arch", "corrupt_digest"]
)
def test_unrelated_or_malformed_images_denied(policy, mutation):
    registry, objects, receipts = image_fixture(
        mutation if mutation in {"revision", "version", "arch"} else None
    )
    if mutation in {"revision", "version", "arch"}:
        # Digests remain internally consistent: the policy must reject the labels themselves.
        pass
    elif mutation == "receipt":
        receipts["amd64"] = "sha256:" + "b" * 64
    elif mutation == "missing_arch":
        index = json.loads(objects[("getfit", VERSION)])
        index["manifests"].pop()
        objects[("getfit", VERSION)] = json.dumps(index).encode()
    else:
        objects[("getfit", receipts["amd64"])] += b" "
    with pytest.raises(policy.Denied):
        policy.verify_image(registry, "getfit", VERSION, SHA, receipts)


def test_malformed_index_schema_denied(policy):
    registry, objects, receipts = image_fixture()
    index = json.loads(objects[("getfit", VERSION)])
    index["schemaVersion"] = 1
    objects[("getfit", VERSION)] = json.dumps(index).encode()
    with pytest.raises(policy.Denied):
        policy.verify_image(registry, "getfit", VERSION, SHA, receipts)
