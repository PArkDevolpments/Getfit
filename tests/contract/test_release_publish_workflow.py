from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_release_is_manual_serialized_and_guarded_before_writes() -> None:
    workflow = ROOT / ".github/workflows/release.yml"
    assert workflow.is_file()
    text = workflow.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in text
    assert "workflow_run:" not in text
    assert "cancel-in-progress: false" in text
    assert "group: getfit-publication" in text
    assert "github.ref == 'refs/heads/main'" in text
    assert "github.event.workflow_run.head_sha" not in text
    assert "skip-existing:" not in text
    assert "latest" not in text
    assert "BUILD_REVISION=${{ github.sha }}" in text
    assert text.count("python _tools/release_policy.py authorize") == 3
    assert "needs: [init, build]" in text
    assert "steps.build.outputs.digest" in text
    assert "actions/upload-artifact@" in text
    assert "actions/download-artifact@" in text
    assert "packages: write" in text
    assert "home-assistant/builder/actions/prepare-multi-arch-matrix" in text
    assert "home-assistant/builder/actions/build-image" in text
    assert "home-assistant/builder/actions/publish-multi-arch-manifest" in text
    assert 'ARCHITECTURES: \'["amd64", "aarch64"]\'' in text
    assert "ghcr.io/ktgregson93-collab/getfit" in text
    assert "docker pull --platform" in text
    assert "verified_digests.index" in text
    assert "release-provenance.json" in text
    assert "${PUBLIC_IMAGE}@${INDEX_DIGEST}" in text
    assert "0.1.0" not in text
