"""Sanitized H6 compatibility gates. Never accepts a remote URL or real credentials.

The loopback proxy harness proves the production Getfit client boundary. The
disposable Core worker proves HA's real WebSocket dispatcher and pinned Pep
service adapter, independently of Supervisor. Neither proves deployed topology.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import importlib.metadata
import io
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from contextlib import asynccontextmanager, redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hwa.integrations.pep import ha_health_service as ha_service  # noqa: E402
from hwa.integrations.pep.service_assertion import ServiceAssertionSigner  # noqa: E402

PROVIDER_SHA = "f61b9644a88c5047176e87d4a7edf2939e218d32"
FAILURES = {
    "NONE",
    "PROXY_CONTRACT_FAILED",
    "DOCKER_UNAVAILABLE",
    "IMAGE_PROVENANCE_UNAVAILABLE",
    "PROVIDER_SOURCE_UNAVAILABLE",
    "CORE_PROTOCOL_FAILED",
    "UNSAFE_REPORT",
}
INVARIANTS = {
    "proxy_harness": (
        "supervisor_endpoint",
        "supervisor_token",
        "assertion_only_command",
        "signature_verified",
        "return_response",
        "envelope_parsed",
        "connection_closed",
    ),
    "core_image": (
        "provider_pinned",
        "service_registered",
        "assertion_only_command",
        "return_response",
        "envelope_parsed",
        "governed_denial",
        "connection_closed",
    ),
}
BUILD_PATTERNS = {
    "getfit_sha": r"[0-9a-f]{40}",
    "provider_sha": r"[0-9a-f]{40}",
    "ha_version": r"[0-9]+\.[0-9]+\.[0-9]+(?:[a-z][0-9]+)?",
    "ha_image_id": r"sha256:[0-9a-f]{64}",
    "ha_image_config_digest": r"sha256:[0-9a-f]{64}",
    "ha_image_tag": (
        r"(?:ghcr\.io/home-assistant/home-assistant|homeassistant/home-assistant)"
        r":[0-9][0-9.a-z-]*"
    ),
    "ha_image_digest": (
        r"(?:ghcr\.io/home-assistant/home-assistant|homeassistant/home-assistant)"
        r"@sha256:[0-9a-f]{64}"
    ),
    "ha_image_index_digest": (
        r"(?:ghcr\.io/home-assistant/home-assistant|homeassistant/home-assistant)"
        r"@sha256:[0-9a-f]{64}"
    ),
}


def new_report(proof: str) -> dict[str, Any]:
    return {
        "proof": proof,
        "build": {"provider_sha": PROVIDER_SHA},
        "passed": False,
        "failure_class": "CORE_PROTOCOL_FAILED"
        if proof == "core_image"
        else "PROXY_CONTRACT_FAILED",
        "invariants": dict.fromkeys(INVARIANTS[proof], False),
    }


def validate_report(report: dict[str, Any]) -> None:
    """Whitelist every artifact field and value, including worker subprocess output."""
    if set(report) != {"proof", "build", "passed", "failure_class", "invariants"}:
        raise ValueError("UNSAFE_REPORT")
    proof = report["proof"]
    if (
        not isinstance(proof, str)
        or proof not in INVARIANTS
        or type(report["passed"]) is not bool
        or report["failure_class"] not in FAILURES
    ):
        raise ValueError("UNSAFE_REPORT")
    build, invariants = report["build"], report["invariants"]
    if not isinstance(build, dict) or not isinstance(invariants, dict):
        raise ValueError("UNSAFE_REPORT")
    if set(invariants) != set(INVARIANTS[proof]):
        raise ValueError("UNSAFE_REPORT")
    if any(type(value) is not bool for value in invariants.values()):
        raise ValueError("UNSAFE_REPORT")
    for key, value in build.items():
        if key not in BUILD_PATTERNS or not isinstance(value, str):
            raise ValueError("UNSAFE_REPORT")
        if re.fullmatch(BUILD_PATTERNS[key], value) is None:
            raise ValueError("UNSAFE_REPORT")
    if build.get("provider_sha") != PROVIDER_SHA:
        raise ValueError("UNSAFE_REPORT")
    if report["passed"] != (all(invariants.values()) and report["failure_class"] == "NONE"):
        raise ValueError("UNSAFE_REPORT")


def _signer(key: Any) -> ServiceAssertionSigner:
    return ServiceAssertionSigner("synthetic-h6-key", key, time.time, lambda: "synthetic-h6-jti")


async def run_proxy_harness(*, scenario: str = "success") -> dict[str, Any]:
    """Use the real runtime factory, signer, client and loopback WebSocket peer."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from websockets.asyncio.client import connect
    from websockets.asyncio.server import serve

    from hwa.domain.identity import PersonContext
    from hwa.runtime import build_pep_health_reader

    report = new_report("proxy_harness")
    checks = report["invariants"]
    key = Ed25519PrivateKey.generate()
    token = "synthetic-h6-supervisor-token"
    subject = "synthetic-h6-ha-user"
    logger = logging.Logger("h6.qa.private")
    logger.disabled = True
    logger.propagate = False

    async def peer(socket: Any) -> None:
        try:
            await socket.send(json.dumps({"type": "auth_required"}))
            auth = json.loads(await socket.recv())
            checks["supervisor_token"] = auth == {"type": "auth", "access_token": token}
            if not checks["supervisor_token"] or scenario == "auth_rejected":
                await socket.send(json.dumps({"type": "auth_invalid"}))
                return
            await socket.send(json.dumps({"type": "auth_ok"}))
            command = json.loads(await socket.recv())
            data = command.get("service_data", {})
            checks["assertion_only_command"] = (
                set(command)
                == {"id", "type", "domain", "service", "service_data", "return_response"}
                and type(command["id"]) is int
                and command["id"] == 1
                and command["type"] == "call_service"
                and command["domain"] == "peptide_site"
                and command["service"] == "get_health_context"
                and set(data) == {"assertion"}
            )
            checks["return_response"] = command.get("return_response") is True
            assertion = data["assertion"]
            header, claims, signature = assertion.split(".")
            key.public_key().verify(
                base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4)),
                f"{header}.{claims}".encode("ascii"),
            )
            decoded = json.loads(base64.urlsafe_b64decode(claims + "=" * (-len(claims) % 4)))
            decoded_header = json.loads(base64.urlsafe_b64decode(header + "=" * (-len(header) % 4)))
            checks["signature_verified"] = (
                decoded_header == {"alg": "EdDSA", "typ": "H0-SA", "kid": "synthetic-h6-key"}
                and set(decoded) == {"iss", "aud", "sub", "iat", "exp", "jti", "kid"}
                and decoded["kid"] == "synthetic-h6-key"
                and decoded["sub"] == subject
                and decoded["iss"] == "getfit"
                and decoded["aud"] == "peptide-health-read"
                and decoded["exp"] - decoded["iat"] == 30
            )
            response = {
                "status_code": 503,
                "body": {"error": "HEALTH_AUTHORITY_DISABLED"},
                "headers": {}
                if scenario == "malformed_envelope"
                else {"Cache-Control": "no-store"},
            }
            await socket.send(
                json.dumps(
                    {
                        "id": 1,
                        "type": "result",
                        "success": True,
                        "result": {"response": response},
                    }
                )
            )
            await socket.wait_closed()
        except Exception:
            # The peer never renders raw frames/exceptions, even on a failed test.
            return

    try:
        async with serve(peer, "127.0.0.1", 0, logger=logger) as server:
            port = server.sockets[0].getsockname()[1]

            @asynccontextmanager
            async def connector(endpoint: str, **options: Any) -> Any:
                checks["supervisor_endpoint"] = endpoint == "ws://supervisor/core/websocket"
                if not checks["supervisor_endpoint"]:
                    raise ValueError("PROXY_CONTRACT_FAILED")
                async with connect(f"ws://127.0.0.1:{port}/core/websocket", **options) as socket:
                    yield socket
                checks["connection_closed"] = socket.transport.is_closing()

            # A seam substitutes only routing to the local protocol peer. Runtime
            # token consumption, private key loading, signing and parsing stay real.
            def client_factory(**options: Any) -> ha_service.HaHealthServiceClient:
                return ha_service.HaHealthServiceClient(connector=connector, **options)

            with tempfile.TemporaryDirectory(prefix="h6-synthetic-") as directory:
                key_file = Path(directory) / "key"
                key_file.write_bytes(base64.urlsafe_b64encode(key.private_bytes_raw()).rstrip(b"="))
                key_file.chmod(0o600)
                with (
                    patch.dict(
                        os.environ,
                        {
                            "HWA_PEP_HEALTH_ENABLED": "true",
                            "SUPERVISOR_TOKEN": token,
                            "HWA_PEP_HEALTH_SIGNING_KEY_FILE": str(key_file),
                            "HWA_PEP_HEALTH_SIGNING_KID": "synthetic-h6-key",
                        },
                    ),
                    patch("hwa.runtime.HaHealthServiceClient", client_factory),
                ):
                    reader = build_pep_health_reader()
                    context = await reader.read(
                        ha_user_id=subject,
                        person=PersonContext(
                            hwa_person_id="synthetic-local",
                            pep_person_id="synthetic-pep",
                            health_profile_id="synthetic-profile",
                            menu_person_id="synthetic-menu",
                            presentation_profile="male",
                            display_name="Synthetic",
                        ),
                    )
                    checks["envelope_parsed"] = (
                        context.status == "UNAVAILABLE"
                        and context.reason == "HEALTH_AUTHORITY_DISABLED"
                        and "SUPERVISOR_TOKEN" not in os.environ
                    )
        if all(checks.values()):
            report.update(passed=True, failure_class="NONE")
    except Exception:
        pass
    return report


async def run_core_worker() -> dict[str, Any]:
    """Exercise actual HA HTTP/WebSocket and Pep production service registration.

    No full Pep boot or Supervisor appliance is implied. Health authority stays
    false. Synthetic verifier/map objects exist only in this disposable process.
    """
    from aiohttp import ClientSession
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from custom_components.peptide_site.health_authority_access_audit import HealthAccessAuditBuffer
    from custom_components.peptide_site.health_authority_assertion import ServiceAssertionVerifier
    from custom_components.peptide_site.health_authority_ha import (
        async_get_health_authority_surfaces,
    )
    from custom_components.peptide_site.health_authority_identity import HealthIdentityMap
    from custom_components.peptide_site.health_authority_transport import HealthAuthorityTransport
    from homeassistant import bootstrap, config_entries, loader
    from homeassistant.core import HomeAssistant
    from homeassistant.core_config import async_process_ha_core_config
    from homeassistant.setup import async_setup_component

    report = new_report("core_image")
    checks = report["invariants"]
    report["build"]["ha_version"] = importlib.metadata.version("homeassistant")
    checks["provider_pinned"] = Path("/probe/provider-sha").read_text() == PROVIDER_SHA
    with tempfile.TemporaryDirectory(prefix="h6-core-") as directory:
        hass = HomeAssistant(directory)
        try:
            config = {"http": {"server_host": "127.0.0.1", "server_port": 18139}}
            # HomeAssistant() alone lacks loader caches, config entries and
            # registries. Follow the pinned Core bootstrap prerequisites before
            # component setup rather than stubbing HA internals for this probe.
            loader.async_setup(hass)
            hass.config.skip_pip = True
            hass.config_entries = config_entries.ConfigEntries(hass, config)
            if not await bootstrap.async_load_base_functionality(hass):
                return report
            await async_process_ha_core_config(
                hass, {"auth_providers": [{"type": "homeassistant"}], "auth_mfa_modules": []}
            )
            if not await async_setup_component(hass, "http", config):
                return report
            if not await async_setup_component(hass, "websocket_api", config):
                return report
            user = await hass.auth.async_create_user("Synthetic H6 QA", group_ids=["system-admin"])
            refresh = await hass.auth.async_create_refresh_token(user, client_id="http://127.0.0.1")
            token = hass.auth.async_create_access_token(refresh)
            key = Ed25519PrivateKey.generate()
            identity = HealthIdentityMap.from_payload(
                {
                    "schema": "peptide-site.health-user-mapping",
                    "schema_version": 1,
                    "mappings": [{"user_id": user.id, "person_id": "synthetic-pep"}],
                },
                allowed_person_ids=["synthetic-pep"],
            )
            verifier = ServiceAssertionVerifier(
                public_keys={"synthetic-h6-key": key.public_key().public_bytes_raw()},
                process_started_monotonic=time.monotonic() - 36,
            )
            transport = HealthAuthorityTransport(
                identity_map=identity,
                assertion_verifier=verifier,
                user_lookup=hass.auth.async_get_user,
                context_provider=lambda person: {},
                audit=HealthAccessAuditBuffer(),
                authority_enabled=False,
                context_validator=lambda payload: False,
            )
            surfaces = await async_get_health_authority_surfaces(hass)
            surfaces.activate(transport)
            checks["service_registered"] = hass.services.has_service(
                "peptide_site", "get_health_context"
            )
            await hass.async_start()
            async with ClientSession() as session:
                async with session.ws_connect("http://127.0.0.1:18139/api/websocket") as socket:
                    if (await socket.receive_json())["type"] != "auth_required":
                        return report
                    await socket.send_json({"type": "auth", "access_token": token})
                    if (await socket.receive_json())["type"] != "auth_ok":
                        return report
                    command = {
                        "id": 1,
                        "type": "call_service",
                        "domain": "peptide_site",
                        "service": "get_health_context",
                        "return_response": True,
                        "service_data": {"assertion": _signer(key).sign(user.id)},
                    }
                    checks["assertion_only_command"] = set(command["service_data"]) == {"assertion"}
                    checks["return_response"] = command["return_response"] is True
                    await socket.send_json(command)
                    frame = await socket.receive_json()
                    # The Getfit production parser validates HA's actual response.
                    envelope = ha_service._envelope(frame)
                    checks["envelope_parsed"] = envelope.headers["Cache-Control"] == "no-store"
                    checks["governed_denial"] = envelope.status_code == 503 and envelope.body == {
                        "error": "HEALTH_AUTHORITY_DISABLED"
                    }
                checks["connection_closed"] = socket.closed
            if all(checks.values()):
                report.update(passed=True, failure_class="NONE")
        finally:
            await hass.async_stop()
    return report


def _command(args: list[str], *, timeout: int = 30) -> bytes:
    return subprocess.run(
        args,
        check=True,
        capture_output=True,
        timeout=timeout,
    ).stdout


def verify_image_provenance(
    path: Path, image_id: str, image_ref: str
) -> tuple[str, str, str, list[str]]:
    """Verify offline official registry document links for a Docker-save import.

    Acquisition is a separate TLS-verified operation. This does not manufacture
    Docker RepoDigests: it returns the hashes of the retained registry bytes.
    """
    provenance = json.loads(path.read_bytes())
    if (
        provenance.get("schema") != "getfit-public-registry-image-acquisition-v1"
        or provenance.get("source_ref") != image_ref
        or provenance.get("platform") != {"os": "linux", "architecture": "amd64"}
        or provenance.get("expected_config_id") != provenance.get("config_digest")
    ):
        raise ValueError("IMAGE_PROVENANCE_UNAVAILABLE")
    documents = {}
    for file_key, digest_key, filename in (
        ("index_file", "index_digest", "official-index.json"),
        (
            "platform_manifest_file",
            "platform_manifest_digest",
            "official-linux-amd64-manifest.json",
        ),
        ("config_file", "config_digest", "official-config.json"),
    ):
        if provenance.get(file_key) != filename:
            raise ValueError("IMAGE_PROVENANCE_UNAVAILABLE")
        raw = (path.parent / filename).read_bytes()
        digest = "sha256:" + hashlib.sha256(raw).hexdigest()
        if digest != provenance.get(digest_key):
            raise ValueError("IMAGE_PROVENANCE_UNAVAILABLE")
        documents[digest_key] = json.loads(raw)
    index = documents["index_digest"]
    manifest = documents["platform_manifest_digest"]
    config = documents["config_digest"]
    descriptors = [
        row
        for row in index["manifests"]
        if row.get("platform", {}).get("os") == "linux"
        and row.get("platform", {}).get("architecture") == "amd64"
    ]
    if (
        len(descriptors) != 1
        or descriptors[0]["digest"] != provenance["platform_manifest_digest"]
        or manifest["config"]["digest"] != provenance["config_digest"]
        or image_id
        not in {
            provenance["config_digest"],
            provenance["platform_manifest_digest"],
            provenance["index_digest"],
        }
    ):
        raise ValueError("IMAGE_PROVENANCE_UNAVAILABLE")
    diff_ids = config["rootfs"]["diff_ids"]
    if (
        not isinstance(diff_ids, list)
        or not diff_ids
        or any(
            not isinstance(value, str) or re.fullmatch(BUILD_PATTERNS["ha_image_id"], value) is None
            for value in diff_ids
        )
    ):
        raise ValueError("IMAGE_PROVENANCE_UNAVAILABLE")
    if "@" in image_ref:
        repository, source_digest = image_ref.split("@", 1)
        if source_digest not in {
            provenance["index_digest"],
            provenance["platform_manifest_digest"],
        }:
            raise ValueError("IMAGE_PROVENANCE_UNAVAILABLE")
    else:
        repository = image_ref.rsplit(":", 1)[0]
    return (
        repository + "@" + provenance["platform_manifest_digest"],
        repository + "@" + provenance["index_digest"],
        provenance["config_digest"],
        diff_ids,
    )


def run_docker_core(
    provider_repo: Path,
    *,
    image_ref: str | None = None,
    wsl_distro: str | None = None,
    image_provenance: Path | None = None,
) -> dict[str, Any]:
    """Inspect an existing local official image; run a separate isolated container.

    An explicit image is supplemental evidence unless independently reconciled
    with Pep's target. This tool never pulls images or changes Docker/WSL config.
    """
    report = new_report("core_image")
    wrapper = ["wsl", "-d", wsl_distro, "--"] if wsl_distro else []
    docker = [*wrapper, "docker"]
    try:
        _command([*docker, "version", "--format", "{{.Server.Version}}"])
    except Exception:
        report["failure_class"] = "DOCKER_UNAVAILABLE"
        return report
    try:
        if image_ref is not None:
            if not any(
                re.fullmatch(BUILD_PATTERNS[key], image_ref)
                for key in ("ha_image_tag", "ha_image_digest")
            ):
                raise ValueError
            image = json.loads(_command([*docker, "image", "inspect", image_ref]))[0]
            image_id = image["Id"]
        else:
            image_id = (
                _command(
                    [
                        *docker,
                        "inspect",
                        "--format",
                        "{{.Image}}",
                        "menu-ha-candidate",
                    ]
                )
                .decode()
                .strip()
            )
            image = json.loads(_command([*docker, "image", "inspect", image_id]))[0]
        if re.fullmatch(BUILD_PATTERNS["ha_image_id"], image_id) is None:
            raise ValueError
        tags = [
            tag
            for tag in image.get("RepoTags", [])
            if re.fullmatch(BUILD_PATTERNS["ha_image_tag"], tag)
        ]
        digests = [
            digest
            for digest in image.get("RepoDigests", [])
            if re.fullmatch(BUILD_PATTERNS["ha_image_digest"], digest)
        ]
        if image["Id"] != image_id:
            raise ValueError
        verified_refs = []
        if image_provenance is not None:
            if image_ref is None:
                raise ValueError
            manifest_digest, index_digest, config_digest, diff_ids = verify_image_provenance(
                image_provenance,
                image_id,
                image_ref,
            )
            if image["RootFS"]["Layers"] != diff_ids:
                raise ValueError
            digests = [manifest_digest]
            verified_refs = [manifest_digest, index_digest]
            report["build"]["ha_image_index_digest"] = index_digest
            report["build"]["ha_image_config_digest"] = config_digest
        if not digests:
            raise ValueError
        if image_ref is not None and image_ref not in [*tags, *digests, *verified_refs]:
            raise ValueError
        if not tags and (not verified_refs or image_ref not in verified_refs):
            raise ValueError
        report["build"].update(
            ha_image_id=image_id,
            ha_image_digest=sorted(digests)[0],
        )
        if tags:
            report["build"]["ha_image_tag"] = sorted(tags)[0]
    except Exception:
        report["failure_class"] = "IMAGE_PROVENANCE_UNAVAILABLE"
        return report
    try:
        archive = _command(
            [
                "git",
                "-C",
                str(provider_repo),
                "archive",
                "--format=tar",
                PROVIDER_SHA,
                "custom_components/peptide_site",
            ]
        )
    except Exception:
        report["failure_class"] = "PROVIDER_SOURCE_UNAVAILABLE"
        return report
    try:
        with tempfile.TemporaryDirectory(prefix="h6-core-probe-") as directory:
            staging = Path(directory)
            with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
                bundle.extractall(staging, filter="data")
            (staging / "provider-sha").write_text(PROVIDER_SHA)
            shutil.copyfile(__file__, staging / "qa_h6_ha_websocket_contract.py")
            shutil.copytree(ROOT / "src" / "hwa", staging / "src" / "hwa")
            mount_path = str(staging)
            if wrapper:
                mount_path = (
                    _command([*wrapper, "wslpath", "-a", "-u", staging.as_posix()]).decode().strip()
                )
            # No host ports, socket, config, tokens, or existing container mounts.
            # The read-only source mount contains only the exact git archive and
            # Getfit source; HA config lives in the disposable container's /tmp.
            raw = _command(
                [
                    *docker,
                    "run",
                    "--rm",
                    "--network",
                    "none",
                    "--cap-drop",
                    "ALL",
                    "--security-opt",
                    "no-new-privileges",
                    "--entrypoint",
                    "python",
                    "--env",
                    "PYTHONPATH=/probe:/probe/src",
                    "--volume",
                    f"{mount_path}:/probe:ro",
                    image_id,
                    "/probe/qa_h6_ha_websocket_contract.py",
                    "--core-worker",
                ],
                timeout=180,
            )
            worker = json.loads(raw)
            validate_report(worker)
            if worker["proof"] != "core_image":
                raise ValueError
            version = worker["build"].get("ha_version")
            matching_tags = [tag for tag in tags if tag.rsplit(":", 1)[1] == version]
            if tags and not matching_tags:
                raise ValueError
            if image_ref in tags and image_ref not in matching_tags:
                raise ValueError
            if matching_tags:
                report["build"]["ha_image_tag"] = sorted(matching_tags)[0]
            worker["build"].update(report["build"])
            return worker
    except Exception:
        # Raw Docker/HA output stays in memory and is discarded.
        return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument(
        "--proxy-harness", action="store_true", help="run the synthetic Supervisor boundary gate"
    )
    modes.add_argument(
        "--docker-core",
        action="store_true",
        help="probe an existing local official HA image in an isolated container",
    )
    modes.add_argument("--core-worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--provider-repo",
        type=Path,
        help="local Pep git repository containing the pinned provider SHA",
    )
    parser.add_argument(
        "--image-ref", help="explicit local official HA version tag or registry digest"
    )
    parser.add_argument(
        "--image-provenance",
        type=Path,
        help="registry document sidecar for a local Docker-save import without RepoDigests",
    )
    parser.add_argument(
        "--wsl-distro",
        choices=["Ubuntu-24.04"],
        help="use Docker in this WSL distro and translate the read-only source mount",
    )
    args = parser.parse_args(argv)
    proof = "proxy_harness" if args.proxy_harness else "core_image"
    report = new_report(proof)
    # Capture third-party output, not just our prints. Only validated JSON can
    # escape this gate. No raw diagnostic artifact is ever written.
    with open(os.devnull, "w") as sink, redirect_stdout(sink), redirect_stderr(sink):
        try:
            if args.proxy_harness:
                report = asyncio.run(run_proxy_harness())
            elif args.core_worker:
                logging.disable(logging.CRITICAL)
                report = asyncio.run(asyncio.wait_for(run_core_worker(), timeout=120))
            elif args.provider_repo is not None:
                report = run_docker_core(
                    args.provider_repo,
                    image_ref=args.image_ref,
                    wsl_distro=args.wsl_distro,
                    image_provenance=args.image_provenance,
                )
            else:
                report["failure_class"] = "PROVIDER_SOURCE_UNAVAILABLE"
            if not args.core_worker:
                try:
                    sha = _command(["git", "-C", str(ROOT), "rev-parse", "HEAD"]).decode().strip()
                    report["build"]["getfit_sha"] = sha
                except Exception:
                    # Preserve the original stable Docker failure when git is
                    # also unavailable; successful reports require provenance.
                    if report["passed"]:
                        raise
            validate_report(report)
        except Exception:
            report = new_report(proof)
            report["failure_class"] = "UNSAFE_REPORT"
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
