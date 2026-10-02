from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "src" / "hwa" / "web" / "templates"
STATIC = ROOT / "src" / "hwa" / "web" / "static"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_acceptance_spec_has_stable_gate_and_criterion_ids() -> None:
    module = _text(ROOT / "src" / "hwa" / "web" / "acceptance.py")

    for gate_id in (
        "GATE-1-TODAY",
        "GATE-2-STRENGTH",
        "GATE-3-TECHNIQUE",
        "GATE-4-CARDIO",
        "GATE-5-PROGRESS",
        "GATE-6-LIBRARY-SETTINGS",
        "GATE-FINAL-REGRESSION",
    ):
        assert gate_id in module

    for criterion_id in (
        "TODAY-01",
        "TODAY-02",
        "STRENGTH-01",
        "STRENGTH-02",
        "TECH-01",
        "CARDIO-01",
        "PROGRESS-01",
        "LIBRARY-01",
        "SETTINGS-01",
        "REGRESSION-01",
    ):
        assert criterion_id in module

    assert "spec_version" in module
    assert "mandatory" in module
    assert "expected" in module
    assert "test_steps" in module
    assert "source" in module


def test_acceptance_page_supports_human_pass_fail_blocked_and_notes() -> None:
    template = _text(TEMPLATES / "acceptance_review.html")
    script = _text(STATIC / "acceptance-review.js")

    assert "Specification & Acceptance" in template
    assert "Pass" in template
    assert "Fail" in template
    assert "Blocked" in template
    assert "Not tested" in template
    assert "Evidence / notes" in template
    assert "Open feature" in template
    assert "Automated checks" in template
    assert "Human checks" in template

    assert "localStorage" in script
    assert "appVersion" in script
    assert "specVersion" in script
    assert "PASS" in script
    assert "FAIL" in script
    assert "BLOCKED" in script
    assert "NOT_TESTED" in script
    assert "updated_at" in script
    assert "criterion_id" in script


def test_review_pack_exports_acceptance_spec_and_results() -> None:
    script = _text(STATIC / "review-capture.js")
    template = _text(TEMPLATES / "review_capture.html")

    assert "acceptance-specification.json" in script
    assert "acceptance-results.json" in script
    assert "getAcceptanceResults" in script
    assert "acceptance_spec" in template
    assert "acceptance_storage_key" in template


def test_settings_exposes_specification_acceptance_tool() -> None:
    settings = _text(TEMPLATES / "settings.html")

    assert "Specification & Acceptance" in settings
    assert "/review-spec" in settings
