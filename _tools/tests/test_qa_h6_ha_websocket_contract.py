"""Run the compatibility gate; reject wrong proxy selection and unsafe artifacts."""

import asyncio
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "_tools" / "qa_h6_ha_websocket_contract.py"


def load_probe():
    assert TOOL.is_file(), "H6 compatibility gate must exist"
    spec = importlib.util.spec_from_file_location("h6_compatibility_probe", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_real_proxy_harness_authenticates_and_parses_without_private_output(capsys, caplog):
    probe = load_probe()
    report = asyncio.run(probe.run_proxy_harness())
    assert report["passed"] is True
    assert report["failure_class"] == "NONE"
    assert report["invariants"] == {
        "supervisor_endpoint": True,
        "supervisor_token": True,
        "assertion_only_command": True,
        "signature_verified": True,
        "return_response": True,
        "envelope_parsed": True,
        "connection_closed": True,
    }
    assert capsys.readouterr().out == ""
    assert caplog.text == ""
    probe.validate_report(report)
    assert "synthetic" not in json.dumps(report)


def test_wrong_endpoint_cannot_satisfy_proxy_proof(monkeypatch):
    probe = load_probe()
    monkeypatch.setattr(probe.ha_service, "_ENDPOINT", "ws://wrong.invalid/core/websocket")
    report = asyncio.run(probe.run_proxy_harness())
    assert report["passed"] is False
    assert report["failure_class"] == "PROXY_CONTRACT_FAILED"
    assert report["invariants"]["supervisor_endpoint"] is False


@pytest.mark.parametrize("scenario", ["auth_rejected", "malformed_envelope"])
def test_denied_auth_or_missing_no_store_cannot_pass(scenario):
    probe = load_probe()
    report = asyncio.run(probe.run_proxy_harness(scenario=scenario))
    assert report["passed"] is False
    assert report["invariants"]["envelope_parsed"] is False
    probe.validate_report(report)


@pytest.mark.parametrize(
    "mutation",
    [
        {"token": "private"},
        {"failure_class": "raw private exception"},
        {"build": {"ha_version": "secret-token"}},
        {"invariants": {"payload": "private"}},
        {"passed": 1},
    ],
)
def test_output_allowlist_rejects_private_or_untyped_fields(mutation):
    probe = load_probe()
    report = probe.new_report("core_image")
    report.update(mutation)
    with pytest.raises(ValueError):
        probe.validate_report(report)


def test_cli_emits_only_sanitized_json_and_success_exit():
    load_probe()
    result = subprocess.run(
        [sys.executable, str(TOOL), "--proxy-harness"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stderr == ""
    report = json.loads(result.stdout)
    assert report["passed"] is True
    assert "synthetic" not in result.stdout


def test_docker_error_discards_raw_command_output(monkeypatch, capsys):
    probe = load_probe()

    def unavailable(*args, **kwargs):
        raise OSError("synthetic-private-token-and-identity")

    monkeypatch.setattr(probe.subprocess, "run", unavailable)
    assert probe.main(["--docker-core", "--provider-repo", str(ROOT)]) == 1
    output = capsys.readouterr()
    assert output.err == ""
    report = json.loads(output.out)
    assert report["failure_class"] == "DOCKER_UNAVAILABLE"
    assert "synthetic-private" not in output.out


@pytest.mark.parametrize("failure", ["missing_digest", "private_worker", "wrong_version"])
def test_core_gate_fails_closed_on_missing_or_inconsistent_provenance(monkeypatch, failure):
    probe = load_probe()
    image_id = "sha256:" + "a" * 64
    worker = probe.new_report("core_image")
    worker["build"]["ha_version"] = "2026.10.1" if failure == "wrong_version" else "2026.10.0"
    worker["invariants"] = dict.fromkeys(worker["invariants"], True)
    worker.update(passed=True, failure_class="NONE")
    if failure == "private_worker":
        worker["body"] = "synthetic-private-payload"
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w"):
        pass
    docker_runs = []

    def external_command(command, **kwargs):
        if command[0] == "git":
            # A mutable provider checkout must never determine installed bytes.
            assert command[4:7] == [
                "--format=tar",
                "f61b9644a88c5047176e87d4a7edf2939e218d32",
                "custom_components/peptide_site",
            ]
            return archive.getvalue()
        if command[1] == "version":
            return b"28.0.0"
        if command[1] == "inspect":
            assert command[-1] == "menu-ha-candidate"
            return image_id.encode()
        if command[1] == "image":
            return json.dumps(
                [
                    {
                        "Id": image_id,
                        "RepoTags": ["ghcr.io/home-assistant/home-assistant:2026.10.0"],
                        "RepoDigests": []
                        if failure == "missing_digest"
                        else [
                            "ghcr.io/home-assistant/home-assistant@sha256:" + "b" * 64,
                        ],
                    }
                ]
            ).encode()
        docker_runs.append(command)
        return json.dumps(worker).encode()

    monkeypatch.setattr(probe, "_command", external_command)
    report = probe.run_docker_core(ROOT)
    assert report["passed"] is False
    assert report["failure_class"] == (
        "IMAGE_PROVENANCE_UNAVAILABLE" if failure == "missing_digest" else "CORE_PROTOCOL_FAILED"
    )
    probe.validate_report(report)
    assert "synthetic-private" not in json.dumps(report)
    if failure == "missing_digest":
        assert docker_runs == []
    else:
        command = docker_runs[0]
        assert command[command.index("--network") + 1] == "none"
        assert command[-3:] == [image_id, "/probe/qa_h6_ha_websocket_contract.py", "--core-worker"]
        assert "-p" not in command and "--publish" not in command


@pytest.mark.skipif(os.getenv("H6_CORE_REGRESSION") != "1", reason="explicit local Core-image gate")
def test_real_core_image_initializes_ha_and_dispatches_pinned_pep_service():
    """Real-image regression for missing loader/config-entry prerequisites."""
    result = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--docker-core",
            "--image-ref",
            "ghcr.io/home-assistant/home-assistant:2026.10.0",
            "--wsl-distro",
            "Ubuntu-24.04",
            "--provider-repo",
            str(ROOT.parent / "Pep-Site-H5"),
            "--image-provenance",
            str(
                ROOT
                / ".superpowers/sdd/2026-10-08-getfit-h6-health-context-production-binding"
                / "image-acquisition/oci-verified-2/provenance.json"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=240,
    )
    assert result.stderr == ""
    report = json.loads(result.stdout)
    assert result.returncode == 0, report["failure_class"]
    assert report["passed"] is True
    assert all(report["invariants"].values())
    assert report["build"]["ha_version"] == "2026.10.0"
    assert report["build"]["provider_sha"] == "f61b9644a88c5047176e87d4a7edf2939e218d32"


@pytest.mark.parametrize(
    "failure", [None, "manifest_bytes", "image_id", "source_ref", "index_ref", "wrong_digest"]
)
def test_imported_image_provenance_requires_linked_registry_documents(tmp_path, failure):
    probe = load_probe()
    config_bytes = (
        b'{"rootfs":{"diff_ids":["sha256:'
        b'cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"]}}'
    )
    config_digest = "sha256:" + hashlib.sha256(config_bytes).hexdigest()
    manifest_bytes = json.dumps({"config": {"digest": config_digest}, "layers": []}).encode()
    manifest_digest = "sha256:" + hashlib.sha256(manifest_bytes).hexdigest()
    index_bytes = json.dumps(
        {
            "manifests": [
                {
                    "platform": {"os": "linux", "architecture": "amd64"},
                    "digest": manifest_digest,
                }
            ]
        }
    ).encode()
    index_digest = "sha256:" + hashlib.sha256(index_bytes).hexdigest()
    provenance = {
        "schema": "getfit-public-registry-image-acquisition-v1",
        "source_ref": "ghcr.io/home-assistant/home-assistant:2026.10.0",
        "platform": {"os": "linux", "architecture": "amd64"},
        "index_digest": index_digest,
        "platform_manifest_digest": manifest_digest,
        "config_digest": config_digest,
        "expected_config_id": config_digest,
        "index_file": "official-index.json",
        "platform_manifest_file": "official-linux-amd64-manifest.json",
        "config_file": "official-config.json",
    }
    (tmp_path / "official-config.json").write_bytes(config_bytes)
    (tmp_path / "official-linux-amd64-manifest.json").write_bytes(
        manifest_bytes + (b" " if failure == "manifest_bytes" else b""),
    )
    (tmp_path / "official-index.json").write_bytes(index_bytes)
    if failure == "source_ref":
        provenance["source_ref"] = "ghcr.io/home-assistant/home-assistant:2026.10.1"
    source_ref = "ghcr.io/home-assistant/home-assistant:2026.10.0"
    if failure in {"index_ref", "wrong_digest"}:
        source_ref = "ghcr.io/home-assistant/home-assistant@" + (
            index_digest if failure == "index_ref" else "sha256:" + "d" * 64
        )
        provenance["source_ref"] = source_ref
    path = tmp_path / "provenance.json"
    path.write_text(json.dumps(provenance))
    image_id = "sha256:" + "d" * 64 if failure == "image_id" else config_digest
    if failure and failure != "index_ref":
        with pytest.raises(ValueError):
            probe.verify_image_provenance(path, image_id, source_ref)
    else:
        verified = probe.verify_image_provenance(
            path, index_digest if failure == "index_ref" else image_id, source_ref
        )
        assert verified == (
            "ghcr.io/home-assistant/home-assistant@" + manifest_digest,
            "ghcr.io/home-assistant/home-assistant@" + index_digest,
            config_digest,
            ["sha256:" + "c" * 64],
        )


def test_core_gate_accepts_verified_index_reference_without_fabricating_tag(monkeypatch):
    probe = load_probe()
    repository = "ghcr.io/home-assistant/home-assistant"
    index = repository + "@sha256:" + "a" * 64
    manifest = repository + "@sha256:" + "b" * 64
    config = "sha256:" + "c" * 64
    layer = "sha256:" + "d" * 64
    worker = probe.new_report("core_image")
    worker["build"]["ha_version"] = "2026.9.4"
    worker["invariants"] = dict.fromkeys(worker["invariants"], True)
    worker.update(passed=True, failure_class="NONE")
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w"):
        pass

    def command(args, **kwargs):
        if args[0] == "git":
            return archive.getvalue()
        if args[1] == "version":
            return b"29.1.3"
        if args[1] == "image":
            return json.dumps(
                [
                    {
                        "Id": index.split("@")[1],
                        "RepoTags": [],
                        "RepoDigests": [index],
                        "RootFS": {"Layers": [layer]},
                    }
                ]
            ).encode()
        return json.dumps(worker).encode()

    monkeypatch.setattr(probe, "_command", command)
    monkeypatch.setattr(
        probe, "verify_image_provenance", lambda *args: (manifest, index, config, [layer])
    )
    result = probe.run_docker_core(ROOT, image_ref=index, image_provenance=ROOT / "sidecar")
    assert result["passed"] is True
    assert "ha_image_tag" not in result["build"]
    assert result["build"]["ha_image_index_digest"] == index
    assert result["build"]["ha_version"] == "2026.9.4"
