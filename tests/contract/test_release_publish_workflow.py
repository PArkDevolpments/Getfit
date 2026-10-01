from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_release_workflow_publishes_verified_home_assistant_multiarch_image() -> None:
    workflow = ROOT / ".github/workflows/release.yml"
    assert workflow.is_file()
    text = workflow.read_text(encoding="utf-8")

    assert 'workflows: ["CI"]' in text
    assert "head_branch == 'main'" in text
    assert "github.event.workflow_run.head_sha" in text
    assert "packages: write" in text
    assert "home-assistant/builder/actions/prepare-multi-arch-matrix" in text
    assert "home-assistant/builder/actions/build-image" in text
    assert "home-assistant/builder/actions/publish-multi-arch-manifest" in text
    assert 'ARCHITECTURES: \'["amd64", "aarch64"]\'' in text
    assert "ghcr.io/ktgregson93-collab/getfit" in text
    assert "docker manifest inspect" in text
    assert "docker pull" in text
    assert "0.1.0" not in text
