"""Fail-closed hosted release guards. This module never writes to external systems."""

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

REPOSITORY = "ktgregson93-collab/Getfit"
NAMESPACE = "ktgregson93-collab"
ARCHES = {"amd64": "amd64", "aarch64": "arm64"}
GATES = ("staging", "compatibility", "security", "rollback")
IMAGES = ("getfit", "amd64-getfit", "aarch64-getfit")
ACCEPT = ", ".join(
    (
        "application/vnd.oci.image.index.v1+json",
        "application/vnd.docker.distribution.manifest.list.v2+json",
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.docker.distribution.manifest.v2+json",
    )
)
JsonAPI = Callable[[str], Any]
Registry = Callable[..., tuple[int, bytes, dict[str, str]]]


class Denied(Exception):
    """No publication is authorized when any guard is uncertain."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise Denied(message)


def privileged(api: JsonAPI, actor: str) -> None:
    require(bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", actor)), "invalid actor")
    permission = api(f"/collaborators/{actor}/permission")
    require(isinstance(permission, dict), "malformed operator permission")
    require(
        permission.get("permission") == "admin"
        or (permission.get("permission") == "write" and permission.get("role_name") == "maintain"),
        "operator requires maintain/admin",
    )


def successful_run(
    api: JsonAPI, run_id: int, sha: str, *, main_push: bool = False
) -> dict[str, Any]:
    run = api(f"/actions/runs/{run_id}")
    require(isinstance(run, dict), "malformed run")
    require(
        run.get("id") == run_id
        and run.get("head_sha") == sha
        and run.get("repository", {}).get("full_name") == REPOSITORY
        and run.get("status") == "completed"
        and run.get("conclusion") == "success",
        "run is not successful at selected SHA",
    )
    if main_push:
        require(
            run.get("event") == "push"
            and run.get("head_branch") == "main"
            and run.get("name") == "CI",
            "CI must be a main push",
        )
    attempt = run.get("run_attempt")
    require(type(attempt) is int and attempt > 0, "missing run attempt")
    jobs = api(f"/actions/runs/{run_id}/attempts/{attempt}/jobs?per_page=100")
    require(isinstance(jobs, dict), "malformed jobs")
    items = jobs.get("jobs")
    require(
        isinstance(items, list) and bool(items) and len(items) == jobs.get("total_count"),
        "incomplete jobs inventory",
    )
    require(
        all(
            isinstance(job, dict)
            and job.get("status") == "completed"
            and job.get("conclusion") == "success"
            and job.get("head_sha") == sha
            for job in items
        ),
        "every gate job must succeed at selected SHA",
    )
    if main_push:
        require(any(job.get("name") == "quality" for job in items), "required quality job missing")
    return cast(dict[str, Any], run)


def authorize(context: dict[str, Any], api: JsonAPI, versions: list[str]) -> str:
    """Authorize original and rerun actors against fresh exact-main API evidence."""
    try:
        sha = context.get("source_sha", "")
        require(context.get("repository") == REPOSITORY, "unexpected repository")
        require(
            context.get("event") == "workflow_dispatch" and context.get("ref") == "refs/heads/main",
            "manual main dispatch required",
        )
        require(
            bool(re.fullmatch(r"[0-9a-f]{40}", sha)) and sha == context.get("sha"),
            "source must equal full dispatch SHA",
        )
        privileged(api, context.get("actor", ""))
        privileged(api, context.get("triggering_actor", ""))
        require(api("/branches/main")["commit"]["sha"] == sha, "main has moved")
        require(
            context.get("auto_update_disabled") == "true",
            "auto-update disabled attestation required",
        )
        require(
            len(versions) == 5
            and len(set(versions)) == 1
            and bool(re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", versions[0]))
            and tuple(map(int, versions[0].split("."))) >= (0, 1, 40),
            "release versions disagree or reuse historical version",
        )
        listing = api("/actions/workflows/ci.yml/runs?event=push&branch=main&per_page=1")
        require(
            isinstance(listing, dict)
            and type(listing.get("total_count")) is int
            and listing["total_count"] > 0,
            "missing main CI",
        )
        runs = listing.get("workflow_runs")
        require(isinstance(runs, list) and len(runs) == 1, "missing latest main CI")
        newest = runs[0]
        require(
            type(newest.get("id")) is int and newest.get("head_sha") == sha,
            "latest main CI is not selected source",
        )
        run = successful_run(api, newest["id"], sha, main_push=True)
        require(run.get("run_attempt") == newest.get("run_attempt"), "CI attempt changed")
        evidence = context.get("evidence")
        require(isinstance(evidence, dict) and set(evidence) == set(GATES), "all evidence required")
        assert isinstance(evidence, dict)
        require(len(set(evidence.values())) == len(GATES), "each gate needs distinct evidence")
        for gate in GATES:
            reference = evidence[gate]
            prefix = re.escape(f"https://github.com/{REPOSITORY}")
            comment_match = re.fullmatch(
                prefix + r"/issues/([1-9][0-9]*)#issuecomment-([1-9][0-9]*)", reference
            )
            require(comment_match is not None, "independent acceptance comment required")
            assert comment_match is not None
            comment = api(f"/issues/comments/{comment_match[2]}")
            require(comment.get("html_url") == reference, "acceptance reference mismatch")
            author = comment["user"]["login"]
            require(
                author not in {context["actor"], context["triggering_actor"]},
                "acceptance must be independently recorded",
            )
            privileged(api, author)
            body = comment.get("body", "")
            lines = body.splitlines()
            require(
                f"release-acceptance: {gate}" in lines
                and f"source-sha: {sha}" in lines
                and "decision: accepted" in lines,
                "missing exact-source named-gate acceptance",
            )
            # Runs can support a reviewer's acceptance, never replace it. Check any
            # same-repository linked runs using the existing exact-source job guard.
            for run_id in re.findall(prefix + r"/actions/runs/([1-9][0-9]*)\b", body):
                successful_run(api, int(run_id), sha)
        require(api("/branches/main")["commit"]["sha"] == sha, "main moved during preflight")
        return versions[0]
    except Denied:
        raise
    except (KeyError, TypeError, ValueError, AttributeError, OSError) as exc:
        raise Denied("malformed or unavailable authorization evidence") from exc


def ensure_absent(registry: Registry, images: list[str] | tuple[str, ...], version: str) -> None:
    for image in images:
        status, raw, _ = registry(image, version)
        try:
            body = json.loads(raw)
            valid_errors = (
                [{"code": "MANIFEST_UNKNOWN", "message": "manifest unknown"}],
                [{"code": "MANIFEST_UNKNOWN"}],
            )
            require(
                status == 404 and isinstance(body, dict) and body.get("errors") in valid_errors,
                f"{image}:{version} exists or absence cannot be established",
            )
        except (ValueError, TypeError) as exc:
            raise Denied("malformed registry absence response") from exc


def document(
    registry: Registry, image: str, ref: str, kind: str = "manifests"
) -> tuple[dict[str, Any], str]:
    status, raw, headers = registry(image, ref, kind)
    require(status == 200, "image is not anonymously readable")
    digest = "sha256:" + hashlib.sha256(raw).hexdigest()
    require(headers.get("Docker-Content-Digest", digest) == digest, "registry digest mismatch")
    if ref.startswith("sha256:"):
        require(digest == ref, "content digest mismatch")
    try:
        result = json.loads(raw)
        require(isinstance(result, dict), "malformed registry document")
        if kind == "manifests":
            require(result.get("schemaVersion") == 2, "unsupported manifest schema")
        return result, digest
    except (ValueError, TypeError) as exc:
        raise Denied("malformed registry document") from exc


def platform_manifest(index: dict[str, Any], platform: str) -> dict[str, Any]:
    entries = index.get("manifests")
    require(isinstance(entries, list), "image index missing manifests")
    assert isinstance(entries, list)
    matching: list[dict[str, Any]] = []
    for entry in entries:
        require(isinstance(entry, dict), "malformed manifest descriptor")
        descriptor = entry.get("platform", {})
        if descriptor.get("os") == "linux" and descriptor.get("architecture") == platform:
            matching.append(entry)
        elif (
            descriptor.get("os") == "unknown"
            and descriptor.get("architecture") == "unknown"
            and entry.get("annotations", {}).get("vnd.docker.reference.type")
            == "attestation-manifest"
        ):
            continue
        else:
            require(
                descriptor.get("os") == "linux"
                and descriptor.get("architecture") in ARCHES.values(),
                "unexpected image platform",
            )
    require(len(matching) == 1, "expected exactly one supported platform manifest")
    return matching[0]


def leaf(
    registry: Registry,
    image: str,
    manifest: dict[str, Any],
    digest: str,
    arch: str,
    version: str,
    sha: str,
) -> str:
    if "manifests" in manifest:
        entry = platform_manifest(manifest, ARCHES[arch])
        digest = entry["digest"]
        manifest, _ = document(registry, image, digest)
    config, _ = document(registry, image, manifest["config"]["digest"], "blobs")
    labels = config["config"]["Labels"]
    require(
        config.get("os") == "linux"
        and config.get("architecture") == ARCHES[arch]
        and labels.get("org.opencontainers.image.revision") == sha
        and labels.get("org.opencontainers.image.version") == version
        and labels.get("io.hass.version") == version
        and labels.get("io.hass.arch") == arch,
        "image revision/version/architecture provenance mismatch",
    )
    return digest


def verify_image(
    registry: Registry,
    image: str,
    version: str,
    sha: str,
    receipts: dict[str, str],
    *,
    architectures_only: bool = False,
) -> dict[str, str]:
    """Join builder receipt roots, architecture manifests/configs and combined index."""
    try:
        required = set(ARCHES) if image == "getfit" else {image.removesuffix("-getfit")}
        require(required <= set(ARCHES) and set(receipts) == required, "build receipts missing")
        leaves = {}
        for arch in required:
            require(
                bool(re.fullmatch(r"sha256:[0-9a-f]{64}", receipts[arch])), "invalid build digest"
            )
            manifest, digest = document(registry, f"{arch}-getfit", version)
            require(digest == receipts[arch], "version tag differs from this build receipt")
            leaves[arch] = leaf(registry, f"{arch}-getfit", manifest, digest, arch, version, sha)
        if image == "getfit" and not architectures_only:
            index, index_digest = document(registry, image, version)
            for arch in ARCHES:
                entry = platform_manifest(index, ARCHES[arch])
                require(entry["digest"] == leaves[arch], "combined index is not this build")
                manifest, digest = document(registry, image, entry["digest"])
                leaf(registry, image, manifest, digest, arch, version, sha)
            leaves["index"] = index_digest
        return leaves
    except Denied:
        raise
    except (KeyError, TypeError, ValueError, AttributeError, OSError) as exc:
        raise Denied("malformed or unavailable image provenance") from exc


def request(url: str, headers: dict[str, str]) -> tuple[int, bytes, dict[str, str]]:
    try:
        with urllib.request.urlopen(
            urllib.request.Request(url, headers=headers), timeout=30
        ) as response:
            return response.status, response.read(), dict(response.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), dict(exc.headers)
    except OSError as exc:
        raise Denied("remote evidence unavailable") from exc


def github_api(path: str) -> Any:
    token = os.environ.get("GH_TOKEN", "")
    require(bool(token), "GitHub authentication required")
    status, raw, _ = request(
        f"https://api.github.com/repos/{REPOSITORY}{path}",
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    require(status == 200, "GitHub evidence request failed")
    try:
        return json.loads(raw)
    except ValueError as exc:
        raise Denied("malformed GitHub response") from exc


def registry_client(authenticated: bool) -> Registry:
    tokens: dict[str, str] = {}

    def fetch(image: str, ref: str, kind: str = "manifests") -> tuple[int, bytes, dict[str, str]]:
        require(image in IMAGES and kind in {"manifests", "blobs"}, "invalid registry target")
        require(
            bool(re.fullmatch(r"(?:[0-9]+\.[0-9]+\.[0-9]+|sha256:[0-9a-f]{64})", ref)),
            "invalid image reference",
        )
        if image not in tokens:
            headers = {}
            if authenticated:
                token = os.environ.get("GH_TOKEN", "")
                actor = os.environ.get("GITHUB_ACTOR", "")
                require(bool(token and actor), "authenticated inventory required")
                basic = base64.b64encode(f"{actor}:{token}".encode()).decode()
                headers["Authorization"] = f"Basic {basic}"
            query = urllib.parse.urlencode(
                {"service": "ghcr.io", "scope": f"repository:{NAMESPACE}/{image}:pull"}
            )
            status, raw, _ = request(f"https://ghcr.io/token?{query}", headers)
            require(status == 200, "registry authentication failed")
            try:
                tokens[image] = json.loads(raw)["token"]
                require(
                    isinstance(tokens[image], str) and bool(tokens[image]), "invalid registry token"
                )
            except (KeyError, ValueError, TypeError) as exc:
                raise Denied("malformed registry token") from exc
        return request(
            f"https://ghcr.io/v2/{NAMESPACE}/{image}/{kind}/{ref}",
            {"Authorization": f"Bearer {tokens[image]}", "Accept": ACCEPT},
        )

    return fetch


def versions(root: Path) -> list[str]:
    patterns = (
        ("getfit/config.yaml", r'^version:\s*"([^"]+)"\s*$'),
        ("Dockerfile", r"^ARG BUILD_VERSION=(\S+)$"),
        ("src/hwa/main.py", r'^APP_VERSION = "([^"]+)"$'),
    )
    result = [
        tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"],
        json.loads((root / "custom_components/getfit_panel/manifest.json").read_text())["version"],
    ]
    for filename, pattern in patterns:
        match = re.search(pattern, (root / filename).read_text(), re.MULTILINE)
        require(match is not None, "missing release version")
        assert match is not None
        result.append(match[1])
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("authorize", "absent", "verify"))
    parser.add_argument("--images", nargs="+", choices=IMAGES, default=list(IMAGES))
    parser.add_argument("--image", choices=IMAGES, default="getfit")
    parser.add_argument("--receipts", type=Path, default=Path("receipts"))
    parser.add_argument("--architectures-only", action="store_true")
    args = parser.parse_args()
    try:
        version = versions(Path.cwd())[0]
        if args.mode == "authorize":
            context: dict[str, Any] = {
                key: os.environ.get(env, "")
                for key, env in {
                    "event": "GITHUB_EVENT_NAME",
                    "ref": "GITHUB_REF",
                    "sha": "GITHUB_SHA",
                    "repository": "GITHUB_REPOSITORY",
                    "actor": "GITHUB_ACTOR",
                    "triggering_actor": "GITHUB_TRIGGERING_ACTOR",
                    "source_sha": "SOURCE_SHA",
                    "auto_update_disabled": "AUTO_UPDATE_DISABLED",
                }.items()
            }
            context["evidence"] = {
                gate: os.environ.get(gate.upper() + "_EVIDENCE", "") for gate in GATES
            }
            version = authorize(context, github_api, versions(Path.cwd()))
            output = os.environ.get("GITHUB_OUTPUT")
            if output:
                with Path(output).open("a", encoding="utf-8") as handle:
                    handle.write(f"version={version}\n")
        elif args.mode == "absent":
            # Both views are mandatory: a public 404 alone can hide a private tag.
            ensure_absent(registry_client(True), args.images, version)
            ensure_absent(registry_client(False), args.images, version)
        else:
            receipts = {}
            for path in args.receipts.glob("*.json"):
                receipt = json.loads(path.read_text())
                require(
                    receipt["source_sha"] == os.environ["SOURCE_SHA"]
                    and receipt["version"] == version
                    and receipt["arch"] not in receipts,
                    "receipt source/version mismatch or duplicate",
                )
                receipts[receipt["arch"]] = receipt["digest"]
            leaves = verify_image(
                registry_client(False),
                args.image,
                version,
                os.environ["SOURCE_SHA"],
                receipts,
                architectures_only=args.architectures_only,
            )
            print(
                json.dumps(
                    {
                        "version": version,
                        "revision": os.environ["SOURCE_SHA"],
                        "verified_digests": leaves,
                    },
                    sort_keys=True,
                )
            )
    except (Denied, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Release denied: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
