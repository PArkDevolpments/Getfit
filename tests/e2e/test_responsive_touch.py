from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_product_shell_has_mobile_viewport_and_touch_sized_controls() -> None:
    base = (ROOT / "src/hwa/web/templates/base.html").read_text(encoding="utf-8")
    app_css = (ROOT / "src/hwa/web/static/app.css").read_text(encoding="utf-8")
    workout_css = (ROOT / "src/hwa/web/static/workout.css").read_text(encoding="utf-8")

    assert 'name="viewport" content="width=device-width, initial-scale=1"' in base
    assert "@media (max-width: 700px)" in app_css
    assert "min-height: 44px" in app_css
    assert "min-height:44px" in workout_css


def test_release_gate_and_ci_container_build_are_permanent_qa() -> None:
    release_gate = ROOT / "docs/operations/release-gate.md"
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert release_gate.is_file()
    text = release_gate.read_text(encoding="utf-8")
    assert "exact-head" in text.lower()
    assert "Kris" in text
    assert "Kirsty" in text
    assert "restart" in text.lower()
    assert "Pep" in text
    assert "docker build" in ci
