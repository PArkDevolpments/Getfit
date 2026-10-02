from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "src" / "hwa" / "web" / "static"
TEMPLATES = ROOT / "src" / "hwa" / "web" / "templates"


def test_review_capture_pack_is_local_and_collects_all_product_surfaces() -> None:
    template = (TEMPLATES / "review_capture.html").read_text(encoding="utf-8")
    script = (STATIC / "review-capture.js").read_text(encoding="utf-8")

    assert "Capture all pages" in template
    assert "Full responsive pack" in template
    assert "getDisplayMedia" not in script
    assert "preferCurrentTab" not in script
    assert "contentDocument" in script
    assert "foreignObject" in script
    assert "XMLSerializer" in script
    assert "image/svg+xml" in script
    assert ".svg" in script
    assert "review-gallery.html" in script
    assert "toBlob" not in script
    assert "getContext(" not in script
    assert "createZip" in script
    assert "getfit-ui-review-" in script
    assert "review-manifest.json" in script
    assert "README.txt" in script
    assert "detectPageState" in script
    assert "page_state" in script
    assert "No active workout" in script
    assert "390" in script
    assert "820" in script
    assert "1440" in script

    # The capture utility must not depend on a third-party CDN or upload endpoint.
    assert "https://" not in template
    assert "XMLHttpRequest" not in script


def test_review_pack_runs_automated_spec_checks_before_building_zip() -> None:
    script = (STATIC / "review-capture.js").read_text(encoding="utf-8")
    template = (TEMPLATES / "review_capture.html").read_text(encoding="utf-8")

    assert "Run automated specification audit" in template
    assert "runAutomatedAudit" in script
    assert "evaluateCriterion" in script
    assert "automated-acceptance-results.json" in script
    assert "automated-review-report.html" in script
    assert "REVIEW_REQUIRED" in script
    assert "BLOCKED" in script
    assert "PASS" in script
    assert "FAIL" in script
    assert "buildAutomatedReport" in script
    assert "No manual pass/fail entry is required before the ZIP is created." in template
