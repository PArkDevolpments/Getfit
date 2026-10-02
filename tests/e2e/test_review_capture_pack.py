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
    assert "createZip" in script
    assert "getfit-ui-review-" in script
    assert "review-manifest.json" in script
    assert "README.txt" in script
    assert "390" in script
    assert "820" in script
    assert "1440" in script

    # The capture utility must not depend on a third-party CDN or upload endpoint.
    assert "https://" not in template
    assert "XMLHttpRequest" not in script
