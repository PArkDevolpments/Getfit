"""Run the compatibility gate; reject wrong proxy selection and unsafe artifacts."""

import asyncio
import importlib.util
import io
import json
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
